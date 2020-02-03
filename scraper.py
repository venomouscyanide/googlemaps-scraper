# -*- coding: utf-8 -*-

"""
    usage: python3 scraper.py --N 100
    where N is the number of reviews to be scraped. Scraper stop when number of reviews is reached OR when the stack contains the
    same number of reviews scraped(meaning no loading of reviews has happened for 20 clicks. The stack size by default is 20).

    Input file is by default urls.txt where the N number of URL's are separated by | (piped)
    Output files to be written to are configured using config.json

"""
from googlemaps import GoogleMaps
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Maps reviews scraper.')
    parser.add_argument('--N', type=int, default=1500, help='Number of reviews to scrape')
    parser.add_argument('--i', type=str, default='urls.txt', help='target URLs file')

    args = parser.parse_args()

    with GoogleMaps(args.N) as scraper:
        with open(args.i, 'r') as urls_file:
            urls = urls_file.read().split('|')
            for index, url in enumerate(urls, 1):
                number_of_tries = 0
                while number_of_tries < 10:
                    try:
                        scraper.get_reviews(url, index)
                        break
                    except:
                        number_of_tries += 1
                        print('Some exception occured. Retrying URL')
                        continue
