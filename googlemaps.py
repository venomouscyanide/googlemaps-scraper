# -*- coding: utf-8 -*-
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import zipfile
import time
import csv, json
import logging
import traceback

from proxy_setup import manifest_json, background_js

GM_WEBPAGE = 'https://www.google.com/maps/'
MAX_WAIT = 10
MAX_RETRY = 10
MAX_TIMES_TO_TRY_LOADING = 20
HEADER = ['id_review', 'caption', 'timestamp', 'retrieval_date', 'rating', 'username', 'n_review_user', 'n_photo_user',
          'url_user']


def _decide_to_continue(stack_for_reviews, number_of_reviews_loaded):
    for stack_element in stack_for_reviews:
        if number_of_reviews_loaded != stack_element:
            return True
    return False


class GoogleMaps:

    def __init__(self, n_max_reviews):
        self.targetfile = None
        self.writer = None

        self.N = n_max_reviews

        self.driver = self.__get_driver()
        self.logger = self.__get_logger()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, tb)

        self.logger.info('Closing chromedriver...')
        self.driver.close()
        self.driver.quit()

        self.targetfile.close()

        return True

    def get_reviews(self, url, index):
        self.writer = self.__get_writer(HEADER, index)

        self.driver.get(url)
        wait = WebDriverWait(self.driver, MAX_WAIT)

        # order reviews by date
        # menu_bt = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.goog-inline-block.section-dropdown-menu-button-caption')))
        menu_bt = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[@data-value=\'Sort\']')))

        # sometimes problem in loading the event on this button
        clicked = False
        tries = 0
        while not clicked and tries < MAX_RETRY:
            try:
                menu_bt.click()
                clicked = True
                time.sleep(2)
            except Exception as e:
                tries += 1
                self.logger.warn('Failed to click recent button')

            # failed to change the filter
            if tries == MAX_RETRY:
                return -1

        # second element of the list: most recent
        recent_rating_bt = self.driver.find_elements_by_xpath('//li[@role=\'menuitemradio\']')[1]
        recent_rating_bt.click()

        # wait to load review (ajax call)
        time.sleep(5)

        n_reviews_loaded = len(self.driver.find_elements_by_xpath('//div[@class=\'section-review-content\']'))
        n_scrolls = 0
        stack_for_reviews = list()

        while n_reviews_loaded < self.N:

            print(f"Number of reviews so far{n_reviews_loaded} and scrolls are {n_scrolls}")
            # scroll to load more reviews
            scrollable_div = self.driver.find_element_by_css_selector(
                'div.section-layout.section-scrollbox.scrollable-y.scrollable-show')
            self.driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)

            # wait for other reviews to load (ajax)
            time.sleep(4)

            # expand review text
            self.__expand_reviews()

            n_reviews_loaded = len(self.driver.find_elements_by_xpath('//div[@class=\'section-review-content\']'))

            if len(stack_for_reviews) < MAX_TIMES_TO_TRY_LOADING:
                stack_for_reviews.insert(0, n_reviews_loaded)
            elif len(stack_for_reviews) == MAX_TIMES_TO_TRY_LOADING:
                if _decide_to_continue(stack_for_reviews, n_reviews_loaded):
                    stack_for_reviews.pop()
                    stack_for_reviews.insert(0, n_reviews_loaded)
                else:
                    break
            print(f"stack is {stack_for_reviews}")
            n_scrolls += 1

        response = BeautifulSoup(self.driver.page_source, 'html.parser')
        reviews = response.find_all('div', class_='section-review-content')

        n_reviews = 0
        for idx, review in enumerate(reviews):
            n_reviews += self.__parse_reviews(review)

        self.logger.info('Scraped %d reviews', n_reviews)

    def __parse_reviews(self, review):

        item = {}

        id_review = review.find('button', class_='section-review-action-menu')['data-review-id']
        username = review.find('div', class_='section-review-title').find('span').text

        try:
            review_text = self.__filter_string(review.find('span', class_='section-review-text').text)
        except Exception as e:
            # print e
            review_text = None

        rating = float(review.find('span', class_='section-review-stars')['aria-label'].split(' ')[1])
        relative_date = review.find('span', class_='section-review-publish-date').text

        try:
            n_reviews_photos = review.find('div', class_='section-review-subtitle').find_all('span')[1].text
            metadata = n_reviews_photos.split('\xe3\x83\xbb')
            if len(metadata) == 3:
                n_photos = int(metadata[2].split(' ')[0].replace('.', ''))
            else:
                n_photos = 0

            idx = len(metadata)
            n_reviews = int(metadata[idx - 1].split(' ')[0].replace('.', ''))

        except Exception as e:
            n_reviews = 0
            n_photos = 0

        user_url = review.find('a')['href']

        item['id_review'] = id_review
        item['caption'] = review_text

        # depends on language, which depends on geolocation defined by Google Maps
        # custom mapping to transform into date shuold be implemented
        item['relative_date'] = relative_date

        # store datetime of scraping and apply further processing to calculate
        # correct date as retrieval_date - time(relative_date)
        item['retrieval_date'] = datetime.now()
        item['rating'] = rating
        item['username'] = username
        item['n_review_user'] = n_reviews
        item['n_photo_user'] = n_photos
        item['url_user'] = user_url

        self.writer.writerow(list(item.values()))

        return 1

    # expand review description
    def __expand_reviews(self):
        # use XPath to load complete reviews
        links = self.driver.find_elements_by_xpath('//button[@class=\'section-expand-review blue-link\']')
        for l in links:
            l.click()
        time.sleep(2)

    def __get_logger(self):
        # create logger
        logger = logging.getLogger('googlemaps-scraper')
        logger.setLevel(logging.DEBUG)

        # create console handler and set level to debug
        fh = logging.FileHandler('gm-scraper.log')
        fh.setLevel(logging.DEBUG)

        # create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # add formatter to ch
        fh.setFormatter(formatter)

        # add ch to logger
        logger.addHandler(fh)

        return logger

    def __get_driver(self, debug=True):
        options = Options()

        options.add_argument("--window-size=1366,768")
        options.add_argument("--disable-notifications")
        options.add_argument('--no-sandbox')
        options.add_argument("--lang=en")

        pluginfile = 'proxy_auth_plugin.zip'

        with zipfile.ZipFile(pluginfile, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        options.add_extension(pluginfile)

        input_driver = webdriver.Chrome(chrome_options=options)

        return input_driver

    def __get_writer(self, header, index):
        self._initialize_target_file(index)

        writer = csv.writer(self.targetfile, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)

        return writer

    # util function to clean special characters
    def __filter_string(self, str):
        strOut = str.replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
        return strOut

    def _initialize_target_file(self, index):
        config = json.load(open('config.json'))
        folder = config['folder']
        self.targetfile = open(folder + config['review-file'] + f"_{index}.csv", mode='w', encoding='utf-8',
                               newline='\n')
