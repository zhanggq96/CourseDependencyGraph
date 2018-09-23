import sqlite3
import pickle
from CourseDependencyGraph.parsers.requisite_parser import RequisiteParseTree


if __name__ == '__main__':
    conn = sqlite3.connect('db/course_db_example.db')
    c = conn.cursor()

    c.execute(
        '''
        SELECT course_id, course_info FROM courses
        LIMIT 3
        '''
    )

    for course_id, course_info in c:
        data = pickle.loads(course_info)
        print(type(data))
        print(data)

    conn.close()