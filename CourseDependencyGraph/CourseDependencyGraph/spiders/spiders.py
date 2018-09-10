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
        # course_code_end = 177132
        # WOMENST 3FF3
        # course_code_end = 178923

        course_code_init = 177776
        course_code_end = 177776
        # course_code_init = 177726
        # course_code_end = 177726

        # old 3dq5
        # course_code_init = 140445
        # course_code_end = 140445

        # new 3dq5
        # course_code_init = course_code_end = 177737 + 5

        # course_code_init = course_code_end = 177800
        
        url_base = 'https://academiccalendars.romcmaster.ca/preview_course_nopop.php?catoid=32&coid='
        
        urls = ('%s%d' % (url_base, cid) for cid in range(course_code_init, course_code_end+1))

        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):

        course_id = response.url.split('=')[-1]
        
        block_content_html = response.css('td.block_content').extract_first()
        acp = RequisitesHTMLParser(block_content_html)
        course_info = acp.extract_info()
        course_info['course_id'] = course_id
        # course_info_html = block_content_html.css('p').extract_first()

        # block_content_html = response.css('td.block_content')
        # course_info_html = block_content_html.extract_first()

        # inspect code and view source produce different results -_-
        # <p> in empty when we parse response (like in inspect code)

        # block_content_html = response.css('td.block_content')
        # block_content = block_content_html.extract_first()

        # course_preview_title_html = block_content_html.css('h1#course_preview_title::text')
        # course_preview_title = course_preview_title_html.extract_first()

        # course_description_html = block_content_html.css('hr::text')
        # course_description = course_description_html.extract_first()

        # requisites_html = block_content_html.css('.block_content > strong::text')
        # requisites = requisites_html.extract()

        # # Titles
        # # https://stackoverflow.com/questions/45313128/scrapy-extracting-data-from-an-html-tag-that-uses-an-id-selector-instead-of-a
        # course_preview_title = course_info_html.css('h1#course_preview_title::text').extract_first()
        # course_code, course_title = course_preview_title.split('-')
        # course_code = course_code.strip()
        # course_title = course_title.strip()
        # # Description
        # course_description_html = course_info_html.css('hr')[0]
        # course_description = course_description_html.text_content()

        # course_info = {
        #     'course_id': course_id,
        #     'course_code': course_code,
        #     'course_title': course_title,
        #     'course_description': course_description,
        # }

        # course_info = {
        #     'course_id': course_id,
        #     'course_preview_title': course_preview_title,
        #     'course_description': course_description,
        #     'requisites': requisites,
        #     'block_content': block_content
        # }

        # converter = html2text.HTML2Text()
        # converter.ignore_links = True

        return course_info

