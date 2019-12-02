# -*- coding: utf-8 -*-

"""
    usage: python3 scraper.py --N 100
    where N is the number of reviews to be scraped. Scroll limit is by default 160. Scraper stop when scroll limit
    OR number of reviews is reached.

    Input file is by default urls.txt where the N number of URL's are separated by | (piped)
    Output files to be written to are configured using config.json

"""
from googlemaps import GoogleMaps
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Maps reviews scraper.')
    parser.add_argument('--N', type=int, default=100, help='Number of reviews to scrape')
    parser.add_argument('--i', type=str, default='urls.txt', help='target URLs file')

    args = parser.parse_args()

    with GoogleMaps(args.N) as scraper:
        with open(args.i, 'r') as urls_file:
            urls = urls_file.read().split('|')
            for index, url in enumerate(urls, 1):
                scraper.get_reviews(url, index)
