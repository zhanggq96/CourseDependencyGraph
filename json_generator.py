import json
import sqlite3
import pickle

from CourseDependencyGraph.parsers.requisite_parser import RequisiteParseTree


def generate_json_file():
    conn = sqlite3.connect('db/course_db_example.db')
    c = conn.cursor()

    c.execute(
        '''SELECT course_id, course_info, coruse_info_json FROM courses_v2'''
    )

    course_data = c.fetchall()

    master_course_graph = {}

    for course_id, course_info, course_info_json in course_data:
        course_info = pickle.loads(course_info)
        course_code = course_info['json_data']['course_code']
        course_graph = {
            'cid': course_id,
            'n': course_code
        }
        # print(course_info['json_data']['course_code'], course_id, type(prereq_rpt), prereq_rpt)

        try:
            prereq_rpt = course_info['rpts']['Prerequisite(s):']
            prereq_graph = prereq_rpt.generate_graph()
            if prereq_graph:
                course_graph = {**course_graph, **prereq_graph}
            print(course_graph)

            master_course_graph[course_code] = course_graph
        except KeyError as ke:
            # print('KeyError for:', course_id, ke)
            pass

    master_course_graph = json.dumps(master_course_graph)
    with open('mcg.js', 'w') as f:
        f.write("var naming = 'compact';\n")
        f.write("var master_course_graph = ")
        f.write(master_course_graph)
        f.write(';')

if __name__ == '__main__':
    generate_json_file()