import scrapy
import sqlite3
import html2text
from CourseDependencyGraph.parsers.Parsers import RequisitesHTMLParser


class AcademicCalenderSpider(scrapy.Spider):
    name = "mac_academic_calender_spider"
    repquisites = {
        'Antirequisite(s):',
        'Prerequisite(s):',
        'Co-requisite(s):',
        'Cross-list(s):'
    }

    def start_requests(self):
        # https://academiccalendars.romcmaster.ca/preview_course_nopop.php?catoid=32&coid=177126

        # # Anthrop 1AA3
        # course_code_init = 177126
        # # Testing purposes
        course_code_init = 177126
        # course_code_end = 177126 + 500
        # WOMENST 3FF3
        course_code_end = 178923

        # course_code_init = 177776
        # course_code_end = 177776
        # course_code_init = 177726
        # course_code_end = 177726

        # old 3dq5
        # course_code_init = 140445
        # course_code_end = 140445

        # new 3dq5
        # course_code_init = course_code_end = 177737 + 5

        # course_code_init = course_code_end = 178767
        
        url_base = 'https://academiccalendars.romcmaster.ca/preview_course_nopop.php?catoid=32&coid='
        
        urls = ('%s%d' % (url_base, cid) for cid in range(
            course_code_init, course_code_end+1))

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):

        course_id = response.url.split('=')[-1]
        
        block_content_html = response.css('td.block_content').extract_first()
        acp = RequisitesHTMLParser(block_content_html, course_id)
        course_info = acp.extract_info()
        course_info['course_id'] = course_id

        return course_info

