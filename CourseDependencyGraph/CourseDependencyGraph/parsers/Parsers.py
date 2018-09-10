import re
from bs4 import BeautifulSoup


class RequisitesHTMLParser():
    ignore_keys = [
        'Print-Friendly Page',
        'Undergraduate Calendar',
        'HELP',
        'Favourites',
        ']',
        '['
    ]

    def __init__(self, block_content_html):
        self.html = block_content_html

    def clean_text(self, text):
        if len(text) <= 1:
            return ''
        text = ' '.join(text.split())
        text = text.strip().strip('\n')
        text = text.replace('\n', '')
        text = text.replace('\xa0', '')
        text = text.replace('\t', ' ')

        return text

    def ignore_text(self, text):
        return any(key in text for key in RequisitesHTMLParser.ignore_keys)

    def split_on_requisites(self, text):
        split = re.split(r'(Prerequisite\(s\):|Antirequisite\(s\):|Co-requisite\(s\):|Cross-list\(s\):)', text, 
                         flags=re.IGNORECASE)
        requisites, requisite_type = split[0::2], split[1::2]
        return requisites, requisite_type

    def extract_info(self):
        root = BeautifulSoup(self.html, features="lxml").find('td', {'class': 'block_content'},
                                                         recursive=True)

        raw_text = self.clean_text(root.getText())
        requisites, requisite_types = self.split_on_requisites(raw_text)
        with open('html_data.html', 'w') as f:
            for requisite in requisites:
                f.write(str(requisite) + '\n')
            for requisite_type in requisite_types:
                f.write(str(requisite_type) + '\n')

        root_children = root.findChildren(['strong', 'a', 'span'], recursive=False)
        # requisites = root_children.getText()

        requisites = {
            'Prerequisite(s):': [],
            'Antirequisite(s):': [],
            'Co-requisite(s):': [],
            'Cross-list(s):': [],
            'Default:': []
        }

        current_requisite = None
        for element in root_children:
            requisite_or_course_list = self.clean_text(element.getText())
            next_sibling = self.clean_text(element.next_sibling)
            # print('Parser child:', requisite_or_course_list)
            # print('Parser next_sibling:', next_sibling)
            if requisite_or_course_list in requisites:
                current_requisite = requisite_or_course_list
                if next_sibling:
                    requisites[current_requisite].append(next_sibling)
            else:
                assert isinstance(requisite_or_course_list, str)
                if requisite_or_course_list: # if not empty
                    if current_requisite in requisites:
                        requisites[current_requisite].append(requisite_or_course_list)
                    else:
                        requisites['Default:'].append(requisite_or_course_list)
                if next_sibling:
                    if current_requisite in requisites:
                        requisites[current_requisite].append(next_sibling)
                    else:
                        requisites['Default:'].append(next_sibling)
        
        for requisite_type, requisite_list in requisites.items():
            print('requisite_type:', requisite_type, requisite_list)
            requisite_list = filter(lambda text: not self.ignore_text(text), requisite_list)
            requisites[requisite_type] = ' '.join(requisite_list)

        course_info = {
            'requisites': requisites,
            'raw_text': raw_text
        }

        return course_info


if __name__ == '__main__':
    html = None
    filename = 'html/academic_calender_html_v4.html'
    with open(filename, 'r') as f:
        html = f.read()
    acp = RequisitesHTMLParser(html)

    course_info = acp.extract_info()
    requisites = course_info['requisites']
    for requisite_type, requisite_info in requisites.items():
        print(requisite_type, requisite_info)