from BeautifulSoup import BeautifulSoup


class AcademicCalenderParser():

    def __init__(self, block_content_html):
        self.html = block_content_html


    def extract_info(self):
        soup = BeautifulSoup(self.html)
        ftags = soup.find_all(['strong', 'a'])
        for element in ftags:
            print(element)


if __name__ == '__main__':
    html = None
    filename = 'academic_calender_html_v2.html'
    with open(filename, 'r') as f:
        html = f.read()
    acp = AcademicCalenderParser(html)

    acp.extract_info()