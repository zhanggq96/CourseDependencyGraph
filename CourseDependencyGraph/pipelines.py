# -*- coding: utf-8 -*-
import json
import sqlite3
import pickle

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html


class CoursedependencygraphPipeline(object):
    def process_item(self, course_info, spider):
        course_id = course_info['json_data']['course_id']
        success_text = 'success' if course_info['json_data']['success'] else 'failed'

        with open('json/processed_data_%s_%s.json' % (course_id, success_text), 'w') as f:
            f.write(json.dumps(course_info['json_data'], indent=4))
            # f.write('from pipelines')
        
        course_info_pdata = pickle.dumps(course_info, pickle.HIGHEST_PROTOCOL)

        conn = sqlite3.connect('db/course_db_example.db')
        c = conn.cursor()

        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS courses_v2
            (
                course_id STRING PRIMARY KEY,
                course_info BLOB,
                coruse_info_json TEXT
            )
            '''
        )

        c.execute(
            '''
            INSERT OR REPLACE INTO courses_v2(course_id, course_info, coruse_info_json)
            VALUES (?, ?, ?)
            ''',
            (course_id, sqlite3.Binary(course_info_pdata), json.dumps(course_info['json_data'], indent=4))
        )

        conn.commit()
        conn.close()

        return None

