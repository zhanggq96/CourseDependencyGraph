import re
import json


class RequisiteParseNode():
    def __init__(self):
        self.children = []
        self.corequisite = False
        self.recommended = False

    @classmethod
    def from_unknown(cls, unknown_node, assert_unknown=True):
        if assert_unknown:
            assert isinstance(unknown_node, RequisiteParseNodeUNKNOWN)
        operator_node = cls()
        operator_node.children = unknown_node.children
        del unknown_node

        return operator_node

    def append(self, item):
        self.children.append(item)

    def extend(self, items):
        self.children.extend(items)

    def length(self):
        return len(self.children)

    def has_single_child(self):
        return self.length() == 1

    def is_leaf(self):
        return len(self.children) == 0

    def flatten(self):
        root, _ = self._flatten()
        root, _ = self._flatten() # Hack to call it twice, but it works
        if isinstance(root, RequisiteParseNodeNote):
            return RequisiteParseNode()
        
        return root

    def _flatten(self):
        if self.has_single_child():
            deepest_child, has_useful_info = self.children[0]._flatten()
            return deepest_child, has_useful_info

        # # Should not be happening - but empty string appears when scraping
        # if isinstance(self, RequisiteParseNodeCourse) and not self.course:
        #     return self, False

        # Don't ignore notes
        # if isinstance(self, RequisiteParseNodeNote) and not self.note:
        #     return self, False

        # Ignore notes
        if isinstance(self, RequisiteParseNodeNote):
            return self, False
        
        if not isinstance(self, (RequisiteParseNodeOR, RequisiteParseNodeAND, RequisiteParseNodeUNKNOWN)):
            return self, True
        
        if not self.children:
            return self, False

        children = []
        for i, child in enumerate(self.children):
            deepest_child, has_useful_info = child._flatten()
            if has_useful_info:
                children.append(deepest_child)
        
        self.children = children
        if self.children:
            return self, True
        else:
            return self, False

    def infer_subject(self):
        _ = self._infer_subject(None)

    def _infer_subject(self, previous_subject):
        # A node is a course iff it is a child, so second condition is redundant.
        if self.is_leaf() and isinstance(self, RequisiteParseNodeCourse):
            self.course = self.course.strip()
            course = self.course
            course_info = course.split(' ')
            if self.has_subject():
                subject = course_info[0]
                if subject == 'ISCI': 
                    # Exclude ISCI
                    return previous_subject
                return subject
            else:
                # assert previous_subject is not None
                if previous_subject is not None:
                    self.insert_subject(previous_subject)
                # else subjectless, likely something went wrong
                return previous_subject
        
        if self.is_leaf() and isinstance(self, RequisiteParseNodeNote):
            return previous_subject

        subject = previous_subject
        for child in self.children:
            subject = child._infer_subject(subject)
        
        return subject
    
    def __repr__(self):
        return str(self.children)

    def _generate_graph(self):
        branch_dict = {}

        if self.corequisite:
            branch_dict['cr'] = 1
        if self.recommended:
            branch_dict['rc'] = 1
        
        courses = []
        subbranches = []
        for child in self.children:
            subbranch_dict = child._generate_graph()
            if isinstance(child, (RequisiteParseNodeOR, RequisiteParseNodeAND)):
                if any(isinstance(subchild, (RequisiteParseNodeOR, RequisiteParseNodeAND, RequisiteParseNodeCourse))
                    for subchild in child.children):
                    subbranches.append(subbranch_dict)
            elif isinstance(child, RequisiteParseNodeCourse):
                courses.append(subbranch_dict)
        
        if courses:
            branch_dict['c'] = courses
        if subbranches:
            branch_dict['s'] = subbranches

        return branch_dict

class RequisiteParseNodeOR(RequisiteParseNode):
    def __init__(self):
        super().__init__()

    def __repr__(self):
        return 'OR:%s' % (str(self.children),)

    def _generate_graph(self):
        branch_dict = super()._generate_graph()
        if not branch_dict:
            # Avoid empty AND/OR nodes
            return {}
        branch_dict['t'] = 'OR'

        return branch_dict

class RequisiteParseNodeAND(RequisiteParseNode):
    def __init__(self):
        super().__init__()

    def __repr__(self):
        return 'AND%s:%s' % ('' if not self.recommended else 'REC', str(self.children),)

    def _generate_graph(self):
        branch_dict = super()._generate_graph()
        if not branch_dict:
            return {}
        branch_dict['t'] = 'AND'

        return branch_dict

class RequisiteParseNodeCourse(RequisiteParseNode):
    def __init__(self, course):
        super().__init__()
        self.course = course

    def has_subject(self):
        course_info = self.course.split(' ')

        # Length 1: must be code
        if len(course_info) == 1:
            return False
        
        # First digit is a number: must be code
        # print('RequisiteParseNodeCourse', self.course, course_info)
        if course_info[0][0] in '0123456789':
            return False

        return True

    def has_course_code(self):
        course_info = self.course.split(' ')
        if len(course_info) == 1:
            return course_info[0][0] in '0123456789'
        else:
            return course_info[0][0] in '0123456789' or course_info[1][0] in '0123456789'

    def insert_subject(self, subject):
        self.course = '%s %s' % (subject, self.course)

    def __repr__(self):
        return str(self.course)
    
    def _generate_graph(self):
        return str(self.course)

class RequisiteParseNodeNote(RequisiteParseNode):
    def __init__(self, note):
        super().__init__()
        self.note = note

    def __repr__(self):
        return '"%s"' % str(self.note)

class RequisiteParseNodeUNKNOWN(RequisiteParseNode):
    def __init__(self):
        super().__init__()
        self.identifier = None

    def __repr__(self):
        return 'UNKNOWN:%s' % (str(self.children),)

class RequisiteParseTree():
    
    digits = '0123456789'
    # These don't need to be handled recursively
    top_level_delimiters = [
        '.', # Should this have a space after it?
        ';'
    ]
    base_level = len(top_level_delimiters)

    # Prefixes must be listed in order of priority
    # e.g. 'credit or registration in one of' must come before 'credit or registration in'
    prefixes = [
        'one of',
        'either',
        'credit or registration in one of',
        'credit or registration in',
        'credit | registration in one of',
        'credit | registration in',
        'registration or credit in',
        'registration | credit in',
        'credit or enrolment in',
        'credit | enrolment in',
        'all of',     # Artificial
        'registration in',
        'completion of',
        'both',
        'including',
    ]
    OR_prefixes = {'one of', 'either', 'credit or registration in one of', 'credit | registration in one of',
                   'registration or credit in one of', 'registration | credit in one of'}

    suffixes = [
        'is recommended',
        'is strongly recommended',
    ]
    prefix_and_suffixes = [
        ('registration in', 'program'),
        ('one of', 'is recommended')
    ]
    infixes = [
        'with a grade of',
    ]
    logical_operators = [
        # Make sure to split on boundaries, don't want to split inside a word
        # To do this, add space at the end
        'and ',
        'or '
    ]
    keywords = [
        'permission', # If permission is detected in a phrase, do something about that
        """Prerequisite(s): ISCI 1A24 A/B; or CHEM 1A03 (or 1E03), 1AA3 and registration in an Honours program; 
        or CHEM 1A03 (or 1E03) and 1AA3 with a grade of at least C-; or CHEM 1A03 (or 1E03), 1AA3 and 
        permission of the Department (see Department Note 2 above.)"""
        'registration',
        'department'
    ]
    replace_dict = {
        ' or, ': ' or , ',

        'credit or registration in one of': 'credit | registration in one of',
        'credit or registration in': 'credit | registration in',
        'registration or credit in': 'registration | credit in',
        'credit or enrolment in': 'credit | enrolment in',
        ', credit | registration': ' and credit | registration',

        'Calculus and Vectors': 'Calculus & Vectors',
        'Data Management and Probability': 'Data Management & Probability',
        'B.H.Sc.': 'BHSc',
        'B.H. Sc.': 'BHSc',
        'B.Sc.': 'BSc',
        'B. Sc.': 'BSc',
        'Engineering and ': 'Engineering & ',
        'Engineering or ': 'Engineering | ',
        'English and': 'English &',
        'Electrical and Biomedical': 'Electrical & Biomedical',
        'Mathematics and Physics': 'Mathematics & Physics',
        'or above': '& above',
        'Arts and Science': 'Arts & Science',
        'BScN.': 'BScN',
        'B.Sc.N.': 'BScN',
        'R.P.N.': 'RPN',
        ' for ': ', ',          # This is a makeshift way to handle for - improve this if get the chance
        ' or Level': ' | Level',
        'III or IV': '3 | 4',
        'prior completion': 'completion',
        'Medical and Biological': 'Medical & Biological',
        'Biology and Genetics': 'Biology & Genetics',

        'MATH 2Z03 and 2ZZ3': 'MATH 2Z03, MATH 2ZZ3', # Causes way too many problems
        'CHEM2OA3': 'CHEM 2OA3',
        'CIVENG 3G03 or 3G04': 'CIVENG 3G03, CIVENG 3G04',

        # changed unit courses (assume eleceng)
        '3TP4 or 3TP3': '3TP3',
        '3TQ4 or 3TQ3': '3TQ3',
        '3DQ4 or 3DQ5': '3DQ5',
        # 'A/Band': 'A/B and',
        # 'A/Bor': 'A/B or'
        # 'both ': 'one of ',
        # 'Both ': 'one of ',
    }
    def __init__(self, requisites, verbose=False, course_code=None, requisite_type='p'):
        self.requisites = requisites
        self.verbose = verbose
        self.course_code = course_code
        self.requisite_type = requisite_type

    def __repr__(self):
        return str('ROOT:[%s]' % (self.root))

    def generate_graph(self):
        if not hasattr(self, 'requisite_type'):
            self.requisite_type = 'p'
        
        course_graph = {
            self.requisite_type: self.root._generate_graph()
        }
        return course_graph
    ### --------------------------------- Procesing Functions

    def find_prefix(self, requisite):
        for prefix in RequisiteParseTree.prefixes:
            p = len(prefix)
            if requisite[0:p].lower() == prefix:
                return prefix, p
        
        return None, None

    def find_suffix(self, requisite):
        for suffix in RequisiteParseTree.suffixes:
            s = len(suffix)
            if requisite[-s:].lower() == suffix:
                return suffix, s
        
        return None, None

    def find_prefix_and_suffix(self, requisite):
        for prefix, suffix in RequisiteParseTree.prefix_and_suffixes:
            p = len(prefix)
            s = len(suffix)
            if requisite[0:p].lower() == prefix and requisite[-s:].lower() == suffix:
                return (prefix, p), (suffix, s)

        return (None, None), (None, None)

    def find_prefix_logical_operator(self, requisite):
        for prefix in RequisiteParseTree.logical_operators:
            p = len(prefix)
            if requisite[0:p].lower() == prefix:
                return prefix, p
        
        return None, None

    def find_ending_brackets_and_replace_text_course(self, requisite_string):
        requisite_cleaned = requisite_string
        try:
            # ending_brackets_text = re.search(r'\((.*?)\)', requisite_string).group(1)
            # requisite_cleaned = re.sub(r'\((.*?)\)', r'', requisite_string)
            opening, closing = requisite_string.rfind('('), requisite_string.rfind(')')
            if opening == -1 and closing == -1:
                ending_brackets_text = ''
            elif closing != len(requisite_string)-1:
                ending_brackets_text = ''
            else:
                ending_brackets_text = requisite_string[opening+1:closing]
                requisite_cleaned = requisite_string[:opening] + requisite_string[closing+1:]
            ending_brackets_text = ending_brackets_text.strip()
        except AttributeError:
            ending_brackets_text = ''
            requisite_cleaned = requisite_string
        return ending_brackets_text, requisite_cleaned

    def find_ending_brackets_and_replace_text_note(self, requisite_string):
        requisite_cleaned = requisite_string
        try:
            # ending_brackets_text = re.search(r'\((.*?)\)', requisite_string).group(1)
            # requisite_cleaned = re.sub(r'\((.*?)\)', r'', requisite_string)
            opening, closing = requisite_string.rfind('('), requisite_string.rfind(')')
            if opening == -1 and closing == -1:
                ending_brackets_text = ''
            elif closing != len(requisite_string)-1:
                ending_brackets_text = ''
            else:
                # Check if stuff in brackets contains a keyword
                ending_brackets_text = requisite_string[opening+1:closing]
                for keyword in RequisiteParseTree.keywords:
                    if keyword.lower() in ending_brackets_text.lower():
                        requisite_cleaned = requisite_string[:opening] + requisite_string[closing+1:]
                        return ending_brackets_text, requisite_cleaned, keyword
                
                # If keyword not found, return originals
                ending_brackets_text = ''
                requisite_cleaned = requisite_string
            ending_brackets_text = ending_brackets_text.strip()
        except AttributeError:
            ending_brackets_text = ''
            requisite_cleaned = requisite_string
        
        return ending_brackets_text, requisite_cleaned, None

    def split_on_period(self, requisite):
        # don't splt gpa (decimal)
        requisite = re.sub(r'(\d*\.\d+)', r'(\1)', requisite)
        split = re.split(r'\.(?![^(]*\))', requisite)
        return split

    def split_on_comma(self, requisite):
        split = re.split(r',|\[comma\]', requisite)
        return split

    def split_on_AND_OR_and_return_which(self, requisite):
        # Important to include these spaces
        # Do not split on anything inside brackets?:
        # https://stackoverflow.com/questions/44425565/how-to-remove-all-characters-not-inside-parentheses-using-regex
        
        split = re.split(r'( \band\b(?![^(]*\)) | \bor\b(?![^(]*\)) |\Aor\b(?![^(]*\))|\Aand\b(?![^(]*\)))', requisite)
        requisites_split, AND_OR_list = split[0::2], split[1::2]
        AND_OR_list = [operator.strip().lower() for operator in AND_OR_list]

        # print('split', split)
        return requisites_split, AND_OR_list

    def split_on_infixes_and_return_which(self, requisite):
        split = re.split('(' + '|'.join(infix for infix in RequisiteParseTree.infixes) + ')', requisite)
        requisites_split, infix_list = split[0::2], split[1::2]

        return requisites_split, infix_list

    def replace_keyword_both(self, requisite):
        """
        Converts: Both MATH 2M03 and 2MM3 (or 2M06), or both MATH 2Z03 and 2ZZ3, or both MATH 2P04 and 2Q04; and registration in any Mechanical Engineering program

        Into: MATH 2M03 ,  2MM3 (or 2M06), or MATH 2Z03 ,  2ZZ3, or MATH 2P04 ,  2Q04; and registration in any Mechanical Engineering program

        This case is unfixable, actually. (or 2M06) will get associated with 2MM3, not both. The only way to deal with this is to write a custom parser for "both" keyword, but I am too lazy for that, and comes with a number of its own design issues as well.
        """
        while 'both ' in requisite.lower():
            t = requisite.lower().find('both ')
            for c in range(t, len(requisite)):
                try:
                    if requisite.lower()[c:c+3] == 'and':
                        # next and found: break, don't keep searching.
                        requisite = requisite[:c] + '[comma] ' + requisite[c+3:]
                        break
                except IndexError:
                    break
            # Replace "both " (sic) with nothing
            requisite = requisite[:t] + requisite[t+5:]
        
        return requisite

    def dfs_replace_unknown_identifier(self, requisite_node, replacement_node_type, identifier):
        if isinstance(requisite_node, RequisiteParseNodeUNKNOWN):
            return replacement_node_type.from_unknown(requisite_node)

        for i, child in enumerate(requisite_node.children):
            requisite_node.children[i] = self.dfs_replace_unknown_identifier(child, replacement_node_type, identifier)

        return requisite_node

    def likely_is_course(self, requisite):
        # Remove all text in brackets first
        requisite_cleaned = re.sub(r'\(.*\)', '', requisite).strip()
        # print('likely_is_course - requisite_cleaned:', requisite_cleaned)

        requisites_split = requisite_cleaned.split(' ')
        if len(requisites_split) > 3:
            return False

        if len(requisites_split) == 1:
            return requisites_split[0][0].isdigit()
        elif len(requisites_split) > 1:
            return requisites_split[1][0].isdigit() or (requisites_split[0][0].isdigit() and requisites_split[1].strip() == 'A/B')
        else:
            return False

    def likely_is_course_prefix_excluded(self, requisite):
        prefix, p = self.find_prefix(requisite)
        requisite_cleaned = requisite[p:]

        return self.likely_is_course(requisite_cleaned)

    def does_not_contain_courses(self, requisite):
        requisites_split = requisite.split(' ')

        for requisite in requisites_split:
            # Length ignoring punctuation
            requisite = requisite.replace('.', '')
            requisite = requisite.replace(',', '')
            requisite = requisite.replace(')', '')
            requisite = requisite.replace('(', '')
            requisite = requisite.replace(';', '')
            if len(requisite) <= 3:
                continue
            
            if len(requisite) == 4:
                if requisite[0].isdigit() and requisite[3].isdigit() and requisite[1].isupper():
                    return False

            if len(requisite) == 5:
                if requisite[0].isdigit() and requisite[3].isdigit() and requisite[4].isdigit() and requisite[1].isupper():
                    return False
              
        return True

    def has_subject(self, course):
        course_info = course.split(' ')

        # Length 1: must be code
        if len(course_info) == 1:
            return False
        
        # First digit is a number: must be code
        # print('RequisiteParseNodeCourse', self.course, course_info)
        if course_info[0][0] in '0123456789':
            return False

        return True

    ### --------------------------------- End Procesing Functions

    #####################

    ### --------------------------------- Postprocesing Functions

    def flatten(self):
        self.root = self.root.flatten()

    def infer_subjects(self):
        self.root.infer_subject()
    
    ### --------------------------------- End Postprocesing Functions

    def process(self):
        if self.verbose: print('root original:', self.requisites)
        self.root = self.preprocess(self.requisites)
        if self.verbose: print('root preprocessed:', self.root)
        self.flatten()
        if self.verbose: print('root flattened:', self.root)
        self.infer_subjects()
        if self.verbose: print('root inferred:', self.root)
        return str(self.root)

    def preprocess(self, requisite):
        requisite_cleaned = requisite
        # replace multiple spaces with one
        # doesn't fix parse problems w/ ENGPHYS 3W04 A/B and PHYSICS 3B06, or ENGPHYS 3BA3 ,  3BB3.
        # requisite_cleaned = ' '.join(requisite_cleaned.split()) 
        requisite_cleaned = re.sub(r'([A-Z]+) ([A-Z]+)', r'\1\2', requisite_cleaned)
        # Treat a units obtained requirement as an OR requirement
        requisite_cleaned = re.sub(r'[A-Za-z0-9]+ units from', 'one of', requisite_cleaned)
        requisite_cleaned = re.sub(r'[aA] grade of [at least ]?[a-dA-D][\+-]* in', '', requisite_cleaned)
        requisite_cleaned = re.sub(r'Students in (.*)at least [A-D][-+] in one of', 'one of', requisite_cleaned)
        
        # One of A, B, C or D pattern to
        # One of A, B, C, D
        or_list_pattern = re.compile(r'([credit or registration in ]*one of (([A-Z]+ )?[1-5][A-Z][A-Z0-9][0-9]+( A/B)?, )*((([A-Z]+ )?)*[1-5][A-Z][A-Z0-9][0-9]+( A/B)?)*) or (([A-Z]+ )?[1-5][A-Z][A-Z0-9][0-9]+( A/B)?)')
        requisites_list = or_list_pattern.findall(requisite_cleaned)

        for i, found_pattern in enumerate(requisites_list):
            pattern_start = found_pattern[0]
            pattern_end = found_pattern[8]
            requisite_pattern_cleaned = ','.join([pattern_start, pattern_end])

            ps = requisite_cleaned.find(pattern_start)
            pe = requisite_cleaned[ps+len(pattern_start):].find(pattern_end) + ps+len(pattern_start) + len(pattern_end)
            # s = requisite_cleaned[ps:pe]
            requisite_cleaned = requisite_cleaned[:ps] + requisite_pattern_cleaned + requisite_cleaned[pe:]

            print('requisite_pattern_cleaned', requisite_pattern_cleaned)
            break # only allow once

        for word, replacement in RequisiteParseTree.replace_dict.items():
            requisite_cleaned = requisite_cleaned.replace(word, replacement)

        # print('preprocess - requisite_cleaned:', requisite_cleaned)
        requisite_cleaned = self.replace_keyword_both(requisite_cleaned)
        if self.verbose:
            print('preprocess - requisite_cleaned:', requisite_cleaned)

        top_level_reference_node = self.top_level_split(requisite_cleaned)
        preprocess_node = top_level_reference_node
        return preprocess_node

    def top_level_split(self, requisite):
        # print('Top level - requisite:\n', requisite)

        top_level_node = RequisiteParseNodeAND()

        requisites_split = self.split_on_period(requisite)
        # print('split on period:', requisites_split)
        # requisites_split = requisite.split('.')
        for requisite in requisites_split:
            if not requisite or requisite is None:
                continue
            
            requisite = requisite.strip()
            second_level_reference_node = self.second_level_split(requisite)
            top_level_node.append(second_level_reference_node)

        return top_level_node

    def second_level_split(self, requisite_string):
        """
        One of xxxx, yyyy is recommended.
        """
        second_level_node = None

        recommended = False
        requisite_cleaned = requisite_string
        # print('second level - requisite_cleaned:', requisite_cleaned)
        
        (prefix, p), (suffix, s) = self.find_prefix_and_suffix(requisite_cleaned)
        if (isinstance(prefix, str) and isinstance(suffix, str)) and (prefix.lower() == 'registration in' and suffix.lower() == 'program') and self.does_not_contain_courses(requisite_cleaned):
            # registration in an Honours Chemistry program
            # Make sure to be able to parse multiple programs (program A OR B)

            programs = requisite_cleaned.strip()
            second_level_node = RequisiteParseNodeNote(programs)
            return second_level_node
        elif (isinstance(prefix, str) and isinstance(suffix, str)) and (prefix.lower() == 'one of' and (suffix.lower() == 'is recommended' or suffix.lower() == 'is strongly recommended')):
            # strip off "is recommended"
            requisite_cleaned = requisite_cleaned[:-s].strip()
            recommended = True
        else:
            prefix, p = self.find_prefix(requisite_string)
            suffix, s = self.find_suffix(requisite_string)
            # print('second level - prefix', prefix, 'credit or registration in' == prefix)

            if prefix is not None or suffix is not None:
                # Remove suffix before prefix
                if suffix is not None:
                    requisite_cleaned = requisite_cleaned[0:-s]
                
                # EDIT: Don't remove prefix in some cases
                if prefix is not None and prefix.lower() in {'one of', 'either', 'including'}:
                    requisite_cleaned = requisite_cleaned
                elif prefix is not None and (prefix.lower() == 'credit | registration in one of' or prefix.lower() == 'registration | credit in one of'):
                    requisite_cleaned = 'one of ' + requisite_cleaned[p:]
                else:
                    requisite_cleaned = requisite_cleaned[p:]
        
        requisite_cleaned = requisite_cleaned.strip()

        # split by semicolon
        requisites = requisite_cleaned.split(';')

        prefixes = []
        reference_nodes = []
        for requisite in requisites:
            requisite = requisite.strip()
            if self.does_not_contain_courses(requisite):
                # print('requisite does not contain course:', requisite)
                prefix, p = self.find_prefix_logical_operator(requisite)
                if prefix is not None:
                    prefix = prefix.strip()
                    requisite = requisite[p:]
                third_level_reference_node = RequisiteParseNodeNote(requisite)
            else:    
                prefix, third_level_reference_node = self.third_level_split(requisite)
            # print('second_level_split - prefix, ref node', prefix)
            # print(third_level_reference_node)
            prefixes.append(prefix)
            reference_nodes.append(third_level_reference_node)

        if prefixes[0] is None and all(prefix == 'or' for prefix in prefixes[1:]):
            second_level_node = RequisiteParseNodeOR()
            second_level_node.extend(reference_nodes)
        elif prefixes[0] is None and all(prefix == 'and' for prefix in prefixes[1:]):
            second_level_node = RequisiteParseNodeAND()
            second_level_node.extend(reference_nodes)
        else:
            # TODO: Handle mix
            # raise ValueError('TODO: mixed contents in bracket for postprocess - operators:', prefixes)

            # Evaluate the AND's and OR's in the order they appear,
            # without any regard for order of operations.
            previous_node = reference_nodes[0]
            for i, prefix in enumerate(prefixes[1:], 1):
                requisite_node = None
                if prefix == 'or':
                    requisite_node = RequisiteParseNodeOR()
                elif prefix == 'and':
                    requisite_node = RequisiteParseNodeAND()
                else:
                    # TODO: None prefix EDIT: Assume 'and'
                    # raise ValueError('Invalid prefix:', prefix, prefixes, requisites)
                    requisite_node = RequisiteParseNodeAND()
                
                requisite_node.append(previous_node)
                requisite_node.append(reference_nodes[i])
                previous_node = requisite_node
            
            # The one from the final iteration
            second_level_node = requisite_node

            # Reverse order to children to maintain sentence structure for subject inference
            # second_level_node.children = requisite_node.children[::-1]
        
        if recommended:
            second_level_node.recommended = True

        # print('second_level_node:', second_level_node)
        return second_level_node

    def third_level_split(self, requisite_string):
        """
        ; -> and ...
        """
        third_level_node = None
        requisite_cleaned = requisite_string
        # print('third level - requisite_cleaned:', requisite_cleaned)
        
        prefix, p = self.find_prefix_logical_operator(requisite_string)
        if prefix is not None:
            prefix = prefix.strip()
            requisite_cleaned = requisite_cleaned[p:]

        requisite_cleaned = requisite_cleaned.strip()

        # It's easy if they are all the same prefix. But what if they are not?
        # Then, associate the AND's first, then the OR's.
        # print('third_level_split - prefix:', prefix)

        fourth_level_reference_node = self.fourth_level_split(requisite_cleaned)
        third_level_node = fourth_level_reference_node
        return prefix, third_level_node

    def fourth_level_split(self, requisite_string):
        """
        Detect "registration in X program"
        """
        fourth_level_node = RequisiteParseNodeAND()

        requisite_cleaned = requisite_string

        (prefix, p), (suffix, s) = self.find_prefix_and_suffix(requisite_cleaned)
        if (isinstance(prefix, str) and isinstance(suffix, str)) and (prefix.lower() == 'registration in' and suffix.lower() == 'program'):
            # Make sure to be able to parse multiple programs (program A OR B)
            # print('fourth level split - prefix/suffix:', prefix, suffix)
            fourth_level_node = RequisiteParseNodeNote(requisite_cleaned)
            # print('fourth_level_node - ', fourth_level_node)
            return fourth_level_node
            # programs = requisite_cleaned[p:-s].strip()

        requisite_cleaned = requisite_cleaned.strip()
        fifth_level_reference_node = self.fifth_level_split(requisite_cleaned)
        fourth_level_node = fifth_level_reference_node
        return fourth_level_node

    def fifth_level_split(self, requisite_string):
        """
        one of ... () -> remove this bracket at end
        But don't remove things like 3G03 (or ISCI 2A18 A/B)
        only things like (see Department Note 2 above.)
        """
        # print('fifth level split - requisite_string:', requisite_string)
        if not requisite_string:
            return ''

        fifth_level_node = RequisiteParseNodeAND()

        requisite_cleaned = requisite_string

        prefix, p = self.find_prefix_logical_operator(requisite_string)
        if prefix is not None:
            # print('fifth level split - prefix:', prefix)
            requisite_cleaned = requisite_cleaned[p:]
        
        note = None

        ending_brackets_text, requisite_cleaned, keyword = \
            self.find_ending_brackets_and_replace_text_note(requisite_cleaned)
        if ending_brackets_text:
            # print('fifth level split - ending_brackets_text:', ending_brackets_text)
            # Don't bother splitting by and/or
            # requisites_split_bracket, AND_OR_list = self.split_on_AND_OR_and_return_which(ending_brackets_text)

            # TODO: How to add this?
            # EDIT: Since it's a note, just AND it.
            note = RequisiteParseNodeNote(ending_brackets_text)
            fifth_level_node.append(note)
        
        sixth_level_reference_node = self.sixth_level_split(requisite_cleaned)
        fifth_level_node.append(sixth_level_reference_node)
        
        # print('fifth_level_node:', fifth_level_node)
        return fifth_level_node

    def sixth_level_split(self, requisite_string):
        """
        and -> one of
        (OR them all)
        """
        sixth_level_node = None

        requisite_cleaned = requisite_string

        prefix, p = self.find_prefix(requisite_string)
        # print('sixth_level_split', requisite_string)
        if prefix is not None:
            requisite_cleaned = requisite_cleaned[p:]
            # if prefix.lower() == 'both':
            #     print('sixth_level_split', prefix)

        requisite_cleaned = requisite_cleaned.strip()
        seventh_level_reference_node = self.seventh_level_split(requisite_cleaned)

        # print('sixth_level_split - prefix', prefix)
        # Take advantage of the fact that "one of" is never nested within each other.
        # It will be evaluated either on this level or the seventh_v2 level below.
        # if prefix is not None:
        #     print('sixth_level_split - prefix', prefix)
        #     print('seventh_level_reference_node', seventh_level_reference_node)
        if prefix is not None and prefix.lower() in RequisiteParseTree.OR_prefixes:
            # for i, child in enumerate(seventh_level_reference_node.children):
            #     for j, grandchild in enumerate(child.children):
            #         seventh_level_reference_node.children[i].children[j] =  RequisiteParseNodeOR.from_unknown(grandchild)
            seventh_level_reference_node = self.dfs_replace_unknown_identifier(seventh_level_reference_node, RequisiteParseNodeOR, identifier='comma_identifier')

            # TODO: Handle cases of 'credit or registration', etc
            # edge should have property 'completed' or 'registration' ?
        else: # elif prefix is not None? Might break it
            # for i, child in enumerate(seventh_level_reference_node.children):
            #     for j, grandchild in enumerate(child.children):
            #         seventh_level_reference_node.children[i].children[j] =  RequisiteParseNodeAND.from_unknown(grandchild)
            seventh_level_reference_node = self.dfs_replace_unknown_identifier(seventh_level_reference_node, RequisiteParseNodeAND, identifier='comma_identifier')

        sixth_level_node = seventh_level_reference_node

        return sixth_level_node 
        
    def seventh_level_split(self, requisite_string):
        """
        XXXX ... () -> remove this bracket at end

        Split on and/or
        Also Needed for: COMPSCI 2C03 or 3DA3 or SFWRENG 2C03 or 3K04
        """
        requisite_cleaned = requisite_string
        # print('sixth level - requisite_string', requisite_string)
        seventh_level_node = None

        # ------------------------------------------
        # Make sure to split on boundaries, don't want to split inside a word
        # This part will have to be rewritten to include whether each was split on an
        # OR or and AND. Basically manually splitting is the easiest way, compared
        # to using re.split and trying to recover or splitting on AND then on OR.
        requisites_split_and_or, AND_OR_list = self.split_on_AND_OR_and_return_which(requisite_cleaned)

        assert len(requisites_split_and_or) == len(AND_OR_list) + 1
        if self.verbose:
            print('seventh_level_split - requisites_split_and_or:', requisites_split_and_or)

        # This stuff breaks everything
        for i, requisite in enumerate(requisites_split_and_or[0:-1]):
            # 'HTHSCI 2D06 A/B, 2E03', 'registration in' from -> 
            #  HTHSCI 2D06 A/B, 2E03,  registration in ...
            # where the 'or' is associated with the commas

            # countercase:
            # MATH 1B03, CHEM 1AA3 and one of MATH 1AA3, 1LT3 ?? -> no
            # print('requisite:', requisite)

            # TODO: Fix this up
            if not (self.likely_is_course(requisite) or self.likely_is_course_prefix_excluded(requisites_split_and_or[i+1])):
                # Fixes Three units of Level I Anthropology or HLTHAGE 1AA3 (HEALTHST 1A03), and registration in Level 3 | 4 of any program. ANTHROP 2E03 is strongly recommended.
                # without breaking requisites = 'MECHENG 4R03, MECHTRON 3DX4, ELECENG 3CL4 or SFWRENG 3DX4'
                
                # print('seventh_level_split - unlikely to be course')
                continue
            if ',' not in requisite or ',' in requisites_split_and_or[i+1]:
                # Ensure comma is middle, not last with the [:-1]?
                # ex. Credit or registration in one of CHEMBIO 2OA3, CHEM 2BA3 or 2OA3, and registration ...

                # another case: One of PSYCH 1F03 or 1X03 , and PSYCH 1XX3 ,
                continue
            prefix, p = self.find_prefix(requisite)
            # print('seventh_level_split - prefix', prefix)
            if prefix is not None:
                # Should include "one of" or not?
                continue

            # Assume if it happens once, it won't happen again
            if AND_OR_list[i] == 'or':
                # print('Found or')
                # .strip(','): Get rid of oxford comma

                requisites_split_and_or = [
                    requisite_or if j < i or j > i+1 else \
                    # extra space after or in replace(',', ' or ') to deal with unspaced commas text
                    ' or '.join([requisites_split_and_or[j].strip(',').replace(',', ' or '), requisites_split_and_or[j+1]]) \
                    for j, requisite_or in enumerate(requisites_split_and_or) \
                    if j != i+1
                ]

                # requisites_split_and_or_cleaned = []
                # for j, requisite_or in enumerate(requisites_split_and_or):
                #     if j == i:
                #         requisites_recombined = ''
                #         requisites_comma_into_or = requisites_split_and_or[j].strip(',').split(',')
                #         requisites_comma_into_or.append(requisites_split_and_or[j+1])

                #         k = len(requisites_comma_into_or) - 1
                #         for requisite_k in requisites_comma_into_or[::-1]:
                #             requisite_k = requisite_k.strip()
                #             requisites_recombined = '%s or %s' % (requisite_k, requisites_recombined)

                #             prefix, p = self.find_prefix(requisite_k)
                #             if prefix is not None and prefix in {'credit | registration in', 'registration | credit in', 'credit | enrolment in'}: 
                #                 break
                #             k -= 1
                        
                #         requisites_split_and_or_cleaned.extend(requisites_comma_into_or[:k])
                #         requisites_split_and_or_cleaned.append(requisites_recombined)
                #     elif j != i+1:
                #         requisites_split_and_or_cleaned.append(requisite_or)

                # requisites_split_and_or = requisites_split_and_or_cleaned

                # Remove from AND_OR_list as well
                AND_OR_list = [operator for j, operator in enumerate(AND_OR_list) if j != i]
                break
            elif AND_OR_list[i] == 'and':
                # print('Found and')
                # .strip(','): Get rid of oxford comma
                requisites_split_and_or = [
                    requisite_and if j < i or j > i+1 else \
                    ' and '.join([requisites_split_and_or[j].strip(',').replace(',', ' and '), requisites_split_and_or[j+1]]) \
                    for j, requisite_and in enumerate(requisites_split_and_or) \
                    if j != i+1
                ]
                AND_OR_list = [operator for j, operator in enumerate(AND_OR_list) if j != i]
                break

        if self.verbose:
            print('seventh_level_split - requisites_split_and_or:', requisites_split_and_or)
            print('seventh_level_split - AND_OR_list:', AND_OR_list)

        if len(AND_OR_list) == 0:
            seventh_level_node = self.seventh_level_v2_split(requisites_split_and_or[0])
        elif all(operator == AND_OR_list[0] for operator in AND_OR_list):
            if AND_OR_list[0] == 'and':
                seventh_level_node = RequisiteParseNodeAND()
            elif AND_OR_list[0] == 'or':
                seventh_level_node = RequisiteParseNodeOR()
            else:
                raise ValueError('seventh_level_split - Unknown operator:', AND_OR_list[0], AND_OR_list)
            
            for requisite in requisites_split_and_or:
                requisite_cleaned = requisite.strip()

                (prefix, p), (suffix, s) = self.find_prefix_and_suffix(requisite_cleaned)
                if (isinstance(prefix, str) and isinstance(suffix, str)) and (prefix.lower() == 'registration in' and suffix.lower() == 'program'):
                    # registration in an Honours Chemistry program
                    # Make sure to be able to parse multiple programs (program A OR B)
                    programs = requisite_cleaned
                    seventh_level_reference_node = RequisiteParseNodeNote(programs)
                else:
                    seventh_level_reference_node = self.seventh_level_v2_split(requisite_cleaned)
                seventh_level_node.append(seventh_level_reference_node)
            
            
            # seventh_level_node.children = seventh_level_node.children[::-1]
        else:
            # raise ValueError('TODO: mixed contents in bracket for seventh_level_split - operators:', AND_OR_list, requisites_split_and_or)
            
            # Reverse order to children to maintain sentence structure for subject inference
            # EDIT: screws up operators order.
            # AND_OR_list = AND_OR_list[::-1]
            # requisites_split_and_or = requisites_split_and_or[::-1]

            operator = AND_OR_list[0]
            if operator == 'or':
                previous_node = RequisiteParseNodeOR()
            elif operator == 'and':
                previous_node = RequisiteParseNodeAND()
            else:
                raise ValueError('Unknown operator:', operator, AND_OR_list)

            # Add the first two manually
            seventh_level_reference_node = self.seventh_level_v2_split(requisites_split_and_or[0])
            previous_node.append(seventh_level_reference_node)
            seventh_level_reference_node = self.seventh_level_v2_split(requisites_split_and_or[1])
            previous_node.append(seventh_level_reference_node)
            
            # Subject inference Partial
            previous_subject = None
            for i, requisite in enumerate(requisites_split_and_or):
                if self.likely_is_course(requisite):
                    # print('seventh_level_split inference:', requisites_split_and_or, requisite, previous_subject)
                    if self.has_subject(requisite):
                        course_info = requisite.split(' ')
                        previous_subject = course_info[0]
                    else:
                        # Possible it is None, because contained in other split
                        # assert previous_subject is not None
                        if previous_subject is not None:
                            requisites_split_and_or[i] = '%s %s' % (previous_subject, requisite)
            # print('Subject inference: requisites_split_and_or', requisites_split_and_or)

            # Then loop
            for operator, requisite in zip(AND_OR_list[1:], requisites_split_and_or[2:]):
                if operator == 'or':
                    requisite_node = RequisiteParseNodeOR()
                    seventh_level_reference_node = self.seventh_level_v2_split(requisite)
                    requisite_node.append(seventh_level_reference_node)
                elif operator == 'and':
                    requisite_node = RequisiteParseNodeAND()
                    seventh_level_reference_node = self.seventh_level_v2_split(requisite)
                    requisite_node.append(seventh_level_reference_node)
                else:
                    raise ValueError('Unknown operator:', operator, AND_OR_list)
                
                requisite_node.append(previous_node)
                previous_node = requisite_node
            
            seventh_level_node = requisite_node
            # Reverse order to children to maintain sentence structure for subject inference
            # print('seventh_level_split - seventh_level_node.children:', seventh_level_node.children)
            # seventh_level_node.children = seventh_level_node.children[::-1]
            # print('seventh_level_split - seventh_level_node.children:', seventh_level_node.children)

        # ------------------------------------------
        # seventh_level_reference_node = self.seventh_level_split(requisite_cleaned)
        # seventh_level_node = seventh_level_reference_node
        # ------------------------------------------

        # print('seventh_level_node:', seventh_level_node)
        return seventh_level_node    

    def seventh_level_v2_split(self, requisite_string):
        """
        and -> one of
        """
        # print('seventh_level_split_v2 - requisite_string:', requisite_string)
        seventh_level_v2_node = None

        requisite_cleaned = requisite_string

        prefix, p = self.find_prefix(requisite_string)
        if prefix is not None:
            requisite_cleaned = requisite_cleaned[p:]

        requisite_cleaned = requisite_cleaned.strip()
        # print('seventh_level_split_v2 - requisite_cleaned:', requisite_cleaned)
        seventh_level_reference_node = self.eighth_level_split(requisite_cleaned)

        # print('seventh_level_split - prefix', prefix)
        # Take advantage of the fact that "one of" is never nested within each other.
        # It will be evaluated either on this level or the sixth level above.
        # if prefix is not None:
        #     print('seventh_level_split - prefix', prefix)
        if prefix is not None and prefix.lower() in RequisiteParseTree.OR_prefixes:
            seventh_level_v2_node = self.dfs_replace_unknown_identifier(seventh_level_reference_node, RequisiteParseNodeOR, identifier='comma_identifier')

            # seventh_level_v2_node = RequisiteParseNodeOR()
            # seventh_level_v2_node.append(seventh_level_reference_node)
        elif prefix is not None and prefix.lower() in {'all of'}:
            seventh_level_v2_node = self.dfs_replace_unknown_identifier(seventh_level_reference_node, RequisiteParseNodeAND, identifier='comma_identifier')

            # seventh_level_v2_node = RequisiteParseNodeAND()
            # seventh_level_v2_node.append(seventh_level_reference_node)
        elif prefix is not None:
            seventh_level_v2_node = self.dfs_replace_unknown_identifier(seventh_level_reference_node, RequisiteParseNodeAND, identifier='comma_identifier')
        else:
            seventh_level_v2_node = seventh_level_reference_node

            # seventh_level_v2_node = RequisiteParseNodeAND()
            # seventh_level_v2_node.append(seventh_level_reference_node)

        # print('seventh_level_v2_node:', seventh_level_v2_node)
        return seventh_level_v2_node 

    def eighth_level_split(self, requisite_string):
        """
        Split by commas.
        The results should all be parented by and AND, unless otherwise specified at end
        """
        eighth_level_node = RequisiteParseNodeUNKNOWN()
        eighth_level_node.identifier = 'comma_operator'

        requisites = self.split_on_comma(requisite_string)
        # print('eighth_level_split - requisites:', requisites)

        for requisite in requisites:
            requisite = requisite.strip()
            ninth_level_reference_node = self.ninth_level_split(requisite)
            # seventh_level_reference_node.append(ninth_level_reference_node)
            # postprocess_reference_node = self.postprocess(requisite)
            eighth_level_node.append(ninth_level_reference_node)

        # print('eighth_level_node:', eighth_level_node)
        return eighth_level_node

    def ninth_level_split(self, requisite_string):
        """
        Handle and, or's
        """
        # print('ninth_level_split - requisite_string:', requisite_string)
        ninth_level_node = None
        requisite_cleaned = requisite_string

        requisites_split_and_or, AND_OR_list = self.split_on_AND_OR_and_return_which(requisite_cleaned)
        # print('ninth_level_split - requisites_split_and_or:', requisites_split_and_or)
        if all(operator == 'and' for operator in AND_OR_list):
            ninth_level_node = RequisiteParseNodeAND()
        elif all(operator == 'or' for operator in AND_OR_list):
            ninth_level_node = RequisiteParseNodeOR()
        else:
            raise ValueError('TODO: mixed contents in bracket for ninth_level_split - operators:', AND_OR_list)

        for requisite in requisites_split_and_or:
            requisite_cleaned = requisite.strip()
            postprocess_reference_node = self.postprocess(requisite_cleaned)
            ninth_level_node.append(postprocess_reference_node)

        # print('ninth_level_node', ninth_level_node)
        return ninth_level_node

    def postprocess(self, requisite_string):
        # For simplicity, assume all infixes require "AND"
        postprocess_reference_node = RequisiteParseNodeAND()

        requisites_split_infix, infix_list = self.split_on_infixes_and_return_which(requisite_string)
        # print('postprocess - requisites_split_infix:', requisites_split_infix)
        # print('postprocess - infix_list:', infix_list)

        for requisite_cleaned in requisites_split_infix:
            if not requisite_cleaned:
                continue

            ending_brackets_text, requisite_cleaned = \
                self.find_ending_brackets_and_replace_text_course(requisite_cleaned)
            # print('postprocess - ending_brackets_text:', ending_brackets_text)
            
            requisite_cleaned = requisite_cleaned.strip()
            prefix, p = self.find_prefix(requisite_string)
            if prefix is not None:
                # print('postprocess - requisite_cleaned w/ prefix:', requisite_cleaned)
                requisite_cleaned = requisite_cleaned[p:].strip()
                # print('postprocess - requisite_cleaned w/o prefix:', requisite_cleaned)
            
            if self.likely_is_course(requisite_cleaned):
                course_node = RequisiteParseNodeCourse(requisite_cleaned)
            else:
                course_node = RequisiteParseNodeNote(requisite_cleaned)
            loop_reference_node = course_node

            # print('postprocess - requisite_cleaned:', requisite_cleaned)
            if ending_brackets_text:
                requisites_split_and_or, AND_OR_list = self.split_on_AND_OR_and_return_which(ending_brackets_text)
                # Remove empty string at beginning
                if not requisites_split_and_or[0]:
                    requisites_split_and_or = requisites_split_and_or[1:]
                
                # print('postprocess - requisites_split_and_or:', requisites_split_and_or)
                # print('postprocess - AND_OR_list:', AND_OR_list)

                # Default to OR for no operator detected
                if len(AND_OR_list) == 0:
                    bracket_course_nodes = [
                        RequisiteParseNodeCourse(course.strip()) if self.likely_is_course(course.strip()) else RequisiteParseNodeNote(course.strip())
                        for course in requisites_split_and_or
                    ]

                    or_node = RequisiteParseNodeOR()
                    or_node.append(course_node)
                    or_node.extend(bracket_course_nodes)
                    loop_reference_node = or_node
                elif all(operator == 'and' for operator in AND_OR_list):
                    bracket_course_nodes = [
                        RequisiteParseNodeCourse(course.strip()) if self.likely_is_course(course.strip()) else RequisiteParseNodeNote(course.strip())
                        for course in requisites_split_and_or
                    ]
                    # for course in bracket_course_nodes:
                    #     if not course.has_course_code():
                    #         course = RequisiteParseNodeNote.from_unknown(course, assert_unknown=False)
                    
                    and_node = RequisiteParseNodeAND()
                    and_node.append(course_node)
                    and_node.extend(bracket_course_nodes)
                    loop_reference_node = and_node
                elif all(operator == 'or' for operator in AND_OR_list):
                    bracket_course_nodes = [
                        RequisiteParseNodeCourse(course.strip()) if self.likely_is_course(course.strip()) else RequisiteParseNodeNote(course.strip())
                        for course in requisites_split_and_or
                    ]
                    # for course in bracket_course_nodes:
                    #     if not course.has_course_code():
                    #         course = RequisiteParseNodeNote.from_unknown(course, assert_unknown=False)

                    or_node = RequisiteParseNodeOR()
                    or_node.append(course_node)
                    or_node.extend(bracket_course_nodes)
                    loop_reference_node = or_node
                else:
                    raise ValueError('TODO: mixed contents in bracket for postprocess - operators:', AND_OR_list)
                    
            # print('loop_reference_node:', loop_reference_node)
            postprocess_reference_node.append(loop_reference_node)

        # print('postprocess_reference_node:', postprocess_reference_node)
        return postprocess_reference_node

    
if __name__ == '__main__':
    # This OR in brackets replaces everything in the semi-colon separated clause
    requisites = ('BIOCHEM 3D03; or BIOCHEM 2EE3 and 3G03 (or ISCI 2A18 A/B);'
                 'or HTHSCI 2D06 A/B or 2E03')
    # requisites = 'CHEM 1A03 (or CHEM 1E03), 1AA3 or ISCI 1A24 A/B'
    # requisites = ('One of MATH 2A03, 2MM3, 2Q04, 2X03, 2Z03, ISCI 2A18 A/B, CHEM YYYY;'
    #              ' and one of MATH 2C03, 2M03, 2P04, 2ZZ3.'
    #              'One of PHYSICS 2B06, 2D03; and XXXX, 2E03 is recommended.')

    # This "or" at the end denotes that the whole list should be OR'd logically
    requisites = ('One of MATH 2A03, 2MM3, 2Q04, 2X03, 2Z03, ISCI 2A18 A/B or CHEM 3YY3;'
                 ' and one of MATH 2C03, 2M03, 2P04, 2ZZ3.'
                 'One of PHYSICS 2B06, 2D03; and XXXX, 2E03 is recommended.')

    # merge nodes representing same courses?
    # requisites = 'ISCI 1A24 A/B; or CHEM 1A03 (or 1E03), 1AA3 and registration in an Honours program; or CHEM 1A03 (or 1E03) and 1AA3 with a grade of at least C- (get permission of prof); or CHEM 1A03 (or 1E03), 1AA3 and permission of the Department (see Department Note 2 above.)'

    # requisites = 'CHEM 1A03 (or 1E03), 1AA3; and one of MATH 1A03, 1LS3, 1X03, 1ZA3; or ISCI 1A24 A/B'
    # requisites = 'CHEM 2LA3 and registration in an Honours Chemistry program'

    # TODO: Handle and, or, etc mix.
    # requisites = 'One of CHEM 2PD3, 2P03, EARTHSC 2L03, ENGINEER 2H03, ENVIRSC 2L03, ISCI 2A18 A/B, MATLS 2B03, PHYSICS 2H04; and one of MATH 1A03, 1LS3, 1X03, 1ZA3, ISCI 1A24 A/B; or permission of the Instructor'
    # requisites = 'One of CHEM 2AA3, CHEMBIO 2A03, 2AA3'
    # requisites = 'CHEM 2PC3; or MATH 1B03 and CHEM 1AA3 and one of MATH 1AA3, 1LT3, 1XX3, 1ZB3; or MATH 1B03 and ISCI 1A24 A/B'
    # There can be logic inside brackets
    # requisites = 'PHYSICS 2B03; and MATH 2X03 (or ISCI 2A18 A/B or MATH 2A03); and credit or registration in MATH 2C03'
    # requisites = 'One of ARTSSCI 1D06 A/B, ISCI 1A24 A/B, MATH 1A03, 1LS3, 1X03, 1ZA3'
    # requisites = 'MATH 2X03 (or 2A03), 2C03, PHYSICS 2H04; or ISCI 2A18 A/B and MATH 2C03; or registration in Honours Mathematics and Physics (B.Sc.) or an Honours Medical and Biological Physics (B.Sc.) program'
    # requisites = 'Registration in an honours AAAAAAA (B.Sc.) program'
    # requisites = 'CHEM 2LA3 and registration in an Honours Chemistry program'
    # requisites = 'One of CHEM 2PD3, 2P03, EARTHSC 2L03 (or 3YY4), ENGINEER 2H03, ENVIRSC 2L03, ISCI 2A18 A/B, MATLS 2B03, PHYSICS 2H04; and one of MATH 1A03, 1LS3, 1X03, 1ZA3, ISCI 1A24 A/B; or permission of the Instructor'
    # requisites = 'COMPSCI 2C03 or 3DA3 or SFWRENG 2C03 or 3K04'
    # requisites = 'BIOCHEM 2B03 (or ISCI 2A18 A/B); and registration in any Honours Biochemistry (B.Sc.) program, Bachelor of Health Sciences (Honours) - Biomedical Sciences Specialization (B.H.Sc.) or Honours Arts & Science and Biochemistry, or registration in Bachelor of Health Sciences (Honours) - Biomedical Discovery and Commercialization (B.H.Sc.)'
    # requisites = 'Credit or registration in one of BIOCHEM 2EE3, 3D03, HTHSCI 2D06 A/B or 2E03'

    # TODO: Handle and, or, etc mix.
    requisites = 'ISCI 1A24 A/B or one of PSYCH 1F03, 1N03, 1X03 and registration in Level II or above; or registration in Level II or above of an Arts & Science or Bachelor of Health Sciences (Honours) (B.H.Sc.) program'

    # requisites = 'XXXX, YYYY, ZZZZ, WWWW and one of AAAA, BBBB; CCCC or DDDD.'

    # requisites = 'PSYCH 2AA3 or 3GG3'
    # requisites = 'One of ANTHROP 2D03, LIFESCI 2D03, PNB 2XC3, PSYCH 2GG3, 2TT3; or BIOLOGY 1A03, 1M03; or BIOLOGY 1M03, HTHSCI 1I06 A/B; or ISCI 1A24 A/B'
    # requisites = 'PNB 2XA3 or PSYCH 2H03; or LINGUIST 1A03, 1AA3; or permission of the instructor'
    # requisites = 'One of BIOLOGY 2C03, 2F03, 3FF3, 3SS3, ISCI 2A18 A/B, LIFESCI 2D03, PNB 2XC3, PSYCH 2TT3'
    # requisites = 'COMMERCE 3MC3; and registration in Level IV of a Commerce program or Level V of an Engineering and Management program'
    # requisites = 'COMMERCE 2FA3 or ECON 2I03; and registration in any Commerce, Engineering and Management, Honours Business Informatics, Honours Actuarial and Financial Mathematics, or four or five-level non-Commerce program'
    # requisites = 'Grade 12 Calculus and Vectors U or MATH 1F03'
    # requisites = 'One of Grade 12 Calculus and Vectors U, MATH 1F03 or a grade of at least B- in MATH 1K03. Physics 5FF7'
    # requisites = 'HTHSCI 2D06 A/B or 2E03 and registration in Level III of the B.H.Sc. (Honours) program; or registration in Level III of the B.H.Sc. (Honours) Specializations'

    # incorrect parsing of "or"?
    # requisites = 'CHEM 1AA3, HTHSCI 1I06 A/B; and HTHSCI 2D06 A/B, 2E03 or registration in Level II of the B.H.Sc. (Honours) Specializations or registration in Level II or above of the Chemical Engineering and Bioengineering or Electrical and Biomedical Engineering'

    # requisites = 'Registration in Level IV of the B.H.Sc. (Honours) program or registration in Level IV of the B.H.Sc. (Honours) Specializations'

    # One of ... and case might be wrong.
    # requisites = 'One of GEOG 2RC3, 2RU3, 2RW3, and registration in Level III or above. Completion of GEOG 1HA3 or 1HB3 is recommended.'

    # requisites = 'Registration in Level III Mechanical Engineering, Mechanical Engineering Co-op (B.Eng.); or Level IV Mechanical Engineering and Management, Mechanical Engineering and Management Co-op (B.Eng.Mgt.) or Mechanical Engineering and Society, Mechanical Engineering and Society Co-op (B.Eng.Society)'
    # requisites = 'ENGINEER 2Q04 or MECHENG 2Q04 or 2QA4 and registration in any Mechanical Engineering or Mechatronics program'
    # requisites = 'Both MATH 2M03 and 2MM3 (or 2M06), or both MATH 2Z03 and 2ZZ3, or both MATH 2P04 and 2Q04; and registration in any Mechanical Engineering program'
    # requisites = 'OSS Grade 11 Mathematics'

    # WTF?
    # requisites = 'Registration in level III or above in any Honours Commerce or Engineering and Management program or Level IV of the Commerce program. Project forms are available from DSB-112.'

    # requisites = 'Permission of B.H.Sc. (Honours) Program'

    # handle 'for' ?
    # requisites = 'NURSING 3TT3 for the B.Sc.N. Basic (A) Stream; or NURSING 3SS3 or 3TT3 for the B.Sc.N. Post Diploma R.P.N. (E) Stream'
    # requisites = 'One of HTHSCI 3C04, NURSING 3SS4, 3SS3 or permission of the instructor'
    # requisites = 'Six units of Level II Indigenous Studies or six units of Level II English and Cultural Studies or permission of the instructor'
    # requisites = 'ECON 2G03 with a grade of at least C+; and ECON 2H03 with a grade of at least C+; and Credit or enrolment in ECON 3U03; or a grade of at least A- in ECON 3WW3; and registration in Level III or Level IV of an Honours Economics program with a GPA of at least 6'
    # requisites = 'ECON 1B03 and 1BB3; or ARTSSCI 2E03 '
    # requisites = 'ENGPHYS 3W04 A/B and PHYSICS 3B06, or both ENGPHYS 3BA3 and 3BB3'
    # requisites = 'ENGPHYS 3W04 A/B and PHYSICS 3B06, or ENGPHYS 3BA3, 3BB3'
    # requisites = 'COMPENG 2DI4 and 2DP4 '
    # requisites = 'Credit or registration in BIOSAFE 1BS0 (or HTHSCI 1BS0); and CHEMBIO 2L03.'
    # requisites = 'Registration in Level IV Honours Chemical Biology (B.Sc.) and permission of the Department; students are responsible for securing a suitable Project Supervisor, and are required to submit an application by March 31st of the academic year prior to registration; students are expected to have a Grade Point Average of at least 7.0'
    # requisites = 'PHYSICS 2D03 or 2E03; and one of ENGPHYS 2A03, 2A04, PHYSICS 2A03, 2B06, 2BB3; PHYSICS 2G03 is strongly recommended'
    # requisites = 'Credit or registration in MATH 3C03, and one of ENGPHYS 2QM3, PHYSICS 2C03, 3M03; or registration in Honours Mathematics and Physics (B.Sc.)'
    # requisites = 'Both MATH 1ZB3 and 1ZC3; or 1ZZ5; or both 1AA3 and 1B03; or both 1H03 and 1NN3'
    # requisites = 'One of SFWRENG 2MX3 or 3MX3'
    # requisites = 'One of ENGPHYS 2E04, SFWRENG 2DA3 or 2DA4; and registration in Level 2 or above of a Mechatronics or Software Engineering - Embedded Systems, Software Engineering - Embedded Systems Co-op (B.Eng.) program'
    # requisites = 'One of ENGINEER 2M04, 2MM3 or 3M03'

    # wtf it actually works?
    # requisites = 'MECHENG 4R03, MECHTRON 3DX4, ELECENG 3CL4 or SFWRENG 3DX4 and registration in any Mechanical Engineering, Mechatronics Engineering or Electrical Engineering program'
    # requisites = 'MECHENG 4R03, MECHTRON 3DX4, ELECENG 3CL4 and SFWRENG 3DX4 and registration in any Mechanical Engineering, Mechatronics Engineering or Electrical Engineering program'


    # requisites = 'ENGINEER 2Q04 or MECHENG 2Q04 or 2QA4 and registration in Level IV or above of any Mechanical Engineering or Mechatronics Engineering program'

    # https://academiccalendars.romcmaster.ca/preview_program.php?catoid=24&poid=14359
    # requisites = 'ECON 2G03 or 2X03; and 2H03; and 2B03 or one of CHEMENG 4C03, COMMERCE 2QA3, POLSCI 3N06 A/B, 3NN3, PNB 2XE3, 3XE3, SOCSCI 2J03, SOCIOL 3H06 A/B, STATS 2D03 or another course that is approved by a departmental counselor as equivalent to ECON 2B03 and enrolment in an Honours Economics program'

    # requisites = 'ARTSSCI 1D06 A/B , MATH 1AA3 , 1LT3 , 1N03, 1NN3, 1XX3 , 1ZZ5'
    # requisites = 'Three units of Anthropology and registration in Level II or above in any program. ANTHROP 2PA3  is strongly recommended.'
    
    # requisites = 'Three units of Level I Anthropology or HLTHAGE 1AA3 (HEALTHST 1A03), and registration in Level III or IV of any program. ANTHROP 2E03 is strongly recommended.'
    # requisites = 'MECHENG 4R03, MECHTRON 3DX4, ELECENG 3CL4 or SFWRENG 3DX4'
    # requisites = 'HISTORY 2DF3'
    # requisites = 'AUTOTECH 3VD3, ENGTECH 3FE3 and one of ENGTECH 3FE3 or 3MN3, and registration in level IV of the Automotive and Vehicle Engineering Technology program'
    # requisites = 'BIOCHEM 2B03, credit or registration in one of CHEMBIO 2OB3, CHEM 2BB3 or 2OB3, and registration in Honours Biochemistry (B.Sc.), Honours Chemical Biology (B.Sc.) or Honours Molecular Biology and Genetics (B.Sc.); or BIOCHEM 2B03 and registration in Honours Arts & Science and Biochemistry or Honours Biophysics (B.Sc.) or Honours Medical and Biological Physics (B.Sc.)'

    # # requisites = 'registration in any program in Anthropology and permission of the instructor.'

    # requisites = 'Registration in Level II or above'
    # requisites = 'ART 3TS3, ART 3GS3, or ART 3GS6 A/B and registration in Level IV Honours Studio Art program'
    # # requisites = 'ART 3TS3, ART 3GS3, and ART 3GS6 A/B and registration in Level IV Honours Studio Art program'

    requisites = 'CHEMENG 2O04 (or CHEMENG 3O04), CHEMENG 3D03 and credit or registration in CHEMENG 3A04 (or CHEMENG 2A04)'
    # requisites = 'MATH 2Z03 and 2ZZ3, and registration or credit in CHEMENG 2F04 and 3D03, or permission of the Department'
    
    # requisites = 'CHEM 2E03, 2OC3, CHEMBIO 2OA3 '
    # requisites = 'CHEM 1A03 (or 1E03) and 1AA3 or ISCI 1A24 A/B; and one of CHEM 2OA3, 2OC3, CHEMBIO 2OA3'

    # requisites = 'COMMERCE 2MA3, 2QA3 and registration in any Commerce or Engineering and Management program; or COMMERCE 2MA3 and one of STATS 2MB3, 3J04, 3N03 or STATS 3Y03'
    # requisites = 'One of COMPENG 3SK3, SFWRENG 3O03, COMPSCI 4TE3 or BIO 1A03'
    # requisites = 'CHEM 1A03 (or 1E03) and 1AA3 or  ISCI 1A24 A/B; and one of CHEM2OA3, 2OC3, CHEMBIO 2OA3 '

    # requisites = 'Nine units of CLASSICS, including CLASSICS 2B03 or registration in Level III or above of an Honours program in Classics'
    
    # requisites = 'AUTOTECH 3MP3, 4AE3, 4EC3, 4MS3, 4TR1, ENGTECH 4EE0, and registration in level IV of the Automotive and Vehicle Engineering Technology program.'

    # requisites = 'Credit or registration in one of CHEMBIO 2OA3, CHEM 2BA3 or 2OA3, and registration in Honours Biochemistry (B.Sc.), Honours Chemical Biology (B.Sc.) or Honours Molecular Biology and Genetics (B.Sc.); or registration in Honours Biophysics (B.Sc.) or Honours Medical and Biological Physics (B.Sc.)'
    # requisites = 'BIOCHEM 2B03, credit or registration in one of CHEMBIO 2OB3, CHEM 2BB3 or 2OB3, and registration in Honours Biochemistry (B.Sc.), Honours Chemical Biology (B.Sc.) or Honours Molecular Biology and Genetics (B.Sc.); or BIOCHEM 2B03 and registration in Honours Arts & Science and Biochemistry or Honours Biophysics (B.Sc.) or Honours Medical and Biological Physics (B.Sc.)'
    
    # requisites = ' ART 3GS3 or ART 3GS6 A/Band registration in Level IV Honours Studio Art program'
    # requisites = 'ART 3TS3, ART 3GS3, or ART 3GS6 A/Band registration in Level IV Honours Studio Art program'
    # requisites = 'One of CLASSICS 1B03,  1M03,2K03, 2LC3,  2LD3, or CLASSICS 3Q03; and registration in Level II or above any program'
    # requisites = 'Three units from CLASSICS 1B03 , 2D03 , 2E03 , 2Y03, 2YY3 ; and registration in Level II or above of any program'

    # requisites = 'CIVENG 3G03 or 3G04 , 3J04 or registration in CIVENG 4N04'

    # requisites = ' ECON 1B03 and registration in any Commerce, Engineering and Management or Honours Business Informatics program; or a grade of at least B+ in one of ARTSSCI 2E03 , ECON 1B03 , 2G03 , 2X03 , and registration in any four or five-level non-Commerce program.'
    
    # requisites = 'CHEM 1A03 (or 1E03 ) and 1AA3 ; or ISCI 1A24 A/B ; and one of 2OA3 , 2OC3 , CHEMBIO 2OA3'

    # requisites = ' One of SOCIOL 3FF3 , 3H06 A/B and enrolment in Level IV of any Honours Sociology program and permission of the instructor'
    
    # requisites = ' Registration in Level III or above of a Communication Studies or Political Science program; or POLSCI 1AA3 and 1AB3 or 1G06 and registration in Level III or above of the Honours Social Psychology (B.A.) program'

    # requisites = ' A grade of A- in both PSYCH 1X03 (or 1F03 ) and PSYCH 1XX3 or ISCI 1A24 A/B ; and registration in Level III or IV of an Honours program; and permission of the instructor/coordinator'
    # requisites = ' One of PSYCH 1F03 or 1X03 , and PSYCH 1XX3 , and one of ARTSSCI 2R03 , COMMERCE 2QA3 , ECON 2B03 , HTHSCI 2A03 , KINESIOL 3C03, LINGUIST 2DD3 , PNB 2XE3 , SOCSCI 2J03 , STATS 2B03 , 2D03 , or credit or registration in HUMBEHV 3HB3 , and registration in Level III or above; or registration in Level III or IV of an ISCI program or B.H.Sc. (Honours) program'
    # requisites = 'credit | registration in one of CHEMBIO 2OB3, CHEM 2BB3,2OB3,'
    
    requisites = ' SOCWORK 2B06 or, both SOCWORK 2BB3 and SOCWORK 2CC3 ; and 2A06 A/B or, both SOCWORK 2C03 and SOCWORK 2D03; and permission of the Department'
    requisites = ' One of SOCIOL 1Z03 , 1A06 A/B and enrollment in Level II or above'
    requisites = ' Registration in a Social Work or Labour Studies program; or SOCWORK 1AA3 or 1BB3 ; and registration in Level III or above of any program'
    
    
    requisites = ' One of LIFESCI 1E03 , MEDPHYS 1E03, MEDRADSC 1C03 , PHYSICS 1AA3 (or 1BA3 or 1BB3 or 1E03 ), 1CC3 , ISCI 1A24 A/B , SCIENCE 1E03; or permission of the instructor'
    
    requisites = ' COMMERCE 1AA3 (or 2AA3); ECON 1B03 ; one of MATH 1A03 , 1LS3 , 1M03, 1N03, 1X03 , 1ZA3 or 1Z04; registration in any Commerce, Engineering and Management, Honours Business Informatics, or Honours Actuarial and Financial Mathematics, or four or five-level non-Commerce program. Students in a four- or five-level non-Commerce program must have at least B- in one of ARTSSCI 2E03 , ECON 1B03 , ECON 2G03 , 2X03 .'
    

    requisites = 'SOCWORK 2B06 or, both SOCWORK 2BB3 and SOCWORK 2CC3; and SOCWORK 2A06 A/B or, both SOCWORK 2C03 and SOCWORK 2D03; and permission of the Departmentv'
    """
    'CHEM 2PC3; or MATH 1B03 and CHEM 1AA3 and one of MATH 1AA3, 1LT3, 1XX3, 1ZB3; or MATH 1B03 and ISCI 1A24 A/B'
    contradicts with req for 
    'Credit or registration in one of BIOCHEM 2EE3, 3D03, HTHSCI 2D06 A/B or 2E03' ?
    ^ its result is still technically correct. May stick with it

    One of GEOG 2RC3, 2RU3, 2RW3, and registration in Level III or above. Completion of GEOG 1HA3 or 1HB3 is recommended.

    """
    rpt = RequisiteParseTree(requisites, verbose=True)
    rpt.process()
