import sys
import re
import json
from bs4 import BeautifulSoup
try:
    from CourseDependencyGraph.parsers.requisite_parser import RequisiteParseTree
except ModuleNotFoundError:
    from requisite_parser import RequisiteParseTree


class RequisitesHTMLParser():
    ignore_keys = [
        'Print-Friendly Page',
        'Undergraduate Calendar',
        'HELP',
        'Favourites',
        ']',
        '['
    ]

    requisite_prefixes = (
        'Prerequisite(s):',
        'Antirequisite(s):',
        'Corequisite(s):',
        'Cross-list(s):'
    )

    def __init__(self, block_content_html, course_id):
        self.html = block_content_html
        self.course_id = course_id

    def clean_text(self, text):
        if len(text) <= 1:
            return ''
        
        # text_split = text.split(' ')
        # print(text_split)
        # text = ' '.join(re.split(r'[\n]{2,}|[\t]+| ', text))

        # split() without arguments is as good as magic.
        text = ' '.join(text.split())
        # text = text.strip(' ')
        text = text.replace('\n', ' ')
        text = text.replace('\xa0', '')
        text = text.replace('\t', ' ')
        text = text.replace('"', '')
        # text = text.replace('[br]', '\n')

        return text.strip(' ')

    def ignore_text(self, text):
        return any(key in text for key in RequisitesHTMLParser.ignore_keys)

    # def split_on_requisites(self, text):
    #     split = re.split(r'(Prerequisite\(s\):|Antirequisite\(s\):|'
    #                      r'Co-requisite\(s\):|Cross-list\(s\):|Back to Top)', text, 
    #                      flags=re.IGNORECASE)
    #     requisites, requisite_type = split[0::2], split[1::2]
    #     return requisites, requisite_type

    def split_on_requisites(self, text):
        # split = text.split('\n')
        split = text.split('[br]')
        # print(split)

        requisites_dict_raw = {}
        for potential_requisite in split:
            potential_requisite = potential_requisite.strip()
            for prefix in RequisitesHTMLParser.requisite_prefixes:
                p = len(prefix)
                # print(potential_requisite[:p], prefix, potential_requisite[:p] == prefix)
                if potential_requisite[:p] == prefix:
                    requisites_dict_raw[prefix] = potential_requisite[p:]

        return requisites_dict_raw

    def extract_info(self):
        print('Extracting info for course id:', self.course_id)

        requisites_dict_raw = {
            'Prerequisite(s):': [],
            'Antirequisite(s):': [],
            'Co-requisite(s):': [],
            'Cross-list(s):': [],
            'Default:': []
        }
        raw_text = ''
        error_msg = ''
        success = True

        # try:
        # TODO: Remove text in <em>
        root = BeautifulSoup(self.html, features="lxml").find('td', {'class': 'block_content'},
                                                        recursive=True)
        for br in root.find_all('br'):
            br.replace_with('[br]')
        # Remove <em> tags and their contents
        em_data = [str(s.extract()) for s in root('em')]

        course_code = 'Unknown'
        course_name = 'XXXX'
        try:
            title = root.find('h1', {'id': 'course_preview_title'}, recursive=True)
            # print('title:', title.getText())
            course_info = title.getText().split('-')
            course_code, course_name = course_info[0], course_info[1]
            course_code = course_code.strip()
            course_name = course_name.strip()
        except (TypeError, AttributeError) as e:
            print('Error parsing course title:', e)
            print('Course id:', self.course_id)
        except ValueError as ve:
            print('Error splitting on course title:', ve)
            print('Course id:', self.course_id)
        # sys.exit()

        raw_text = self.clean_text(root.getText())
        # print(raw_text)
        requisites_dict_raw = self.split_on_requisites(raw_text)
        # with open('html_data.html', 'w') as f:
        #     for requisite_type, requisite in requisites_dict_raw.items():
        #         f.write(requisite_type)
        #         f.write(requisite + '\n')
        
        # print(requisites_dict_raw)
        # requisite_types.insert(0, 'Default:')
        rpts = {}
        requisites_dict_processed = {}
        for requisite_type, requisite in requisites_dict_raw.items():
            # print(requisite_type, requisite)
            if requisite_type in requisites_dict_raw:
                # print('Current requisite:', requisite_type, requisite)
                rpt = RequisiteParseTree(requisite, verbose=False, course_code=course_code)
                rpts[requisite_type] = rpt
                requisite_processed = rpt.process()
                requisites_dict_processed[requisite_type] = requisite_processed
        # except AssertionError as ae:
        #     print('Assertion Error:', ae)
        #     error_msg = str('assertion error:') + str(ae)
        # except ValueError as ve:
        #     print('Value Error:', ve)
        #     error_msg = str('valuue error:') + str(ve)
        # except Exception as ex:
        #     print('Exception handling:', ex)
        #     error_msg = str(ex)
        #     success = False

        course_info = {
            'json_data': {
                'course_id': self.course_id,
                'course_name': course_name,
                'course_code': course_code,
                'requisites_dict_raw': requisites_dict_raw,
                'requisites_dict_processed': requisites_dict_processed,
                'raw_text': raw_text,
                'em_data': em_data,
                'success': success,
                'error_msg': error_msg,
            },
            'rpts': rpts
        }

        # success_text = 'success' if success else 'failed'
        # with open('json/processed_data_%s_%s.json' % (self.course_id, success_text), 'w') as f:
        #     f.write(json.dumps(course_info, indent=4))

        return course_info


if __name__ == '__main__':
    html = None
    filename = 'html/academic_calender_html_compeng3sk3.html'
    with open(filename, 'r') as f:
        html = f.read()
    acp = RequisitesHTMLParser(html, 0)

    course_info = acp.extract_info()
    requisites = course_info['json_data']['requisites_dict_raw']
    for requisite_type, requisite_info in requisites.items():
        print(requisite_type, requisite_info)

    course_code = course_info['json_data']['course_code']
    print('course_code:', course_code)