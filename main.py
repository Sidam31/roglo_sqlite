#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup

import urllib.parse
import requests
import sqlite3
import time
import json
import sys
import re
import os

class DB:
    path = os.path.dirname(os.path.realpath(__file__))
    con = sqlite3.connect(path + '/db.sqlite3')
    cur = con.cursor()

    def update():
        DB.cur.execute('CREATE TABLE IF NOT EXISTS people (firstname TEXT NOT NULL DEFAULT "", lastname TEXT NOT NULL DEFAULT "", sex TEXT, birthdate DATE, birthplace TEXT, deathdate DATE, deathplace TEXT, permalink TEXT PRIMARY KEY, family_id INT, CONSTRAINT `unique_permalink` UNIQUE(permalink) ON CONFLICT REPLACE)')
        DB.cur.execute('CREATE TABLE IF NOT EXISTS family (id TEXT PRIMARY KEY, father_permalink TEXT, mother_permalink TEXT, wedding_date DATE, wedding_place TEXT, CONSTRAINT `unique_id` UNIQUE(id) ON CONFLICT REPLACE)')
        DB.con.commit()

class Process:
    base = 'http://roglo.eu/roglo?'

    def __init__(self, filename):
        self.filename = filename
        self.cache = {}

    def init_caches(self):
        if not len(self.cache) and os.path.isfile(self.filename) and os.path.getmtime(self.filename) > time.time() - 12 * 3600 and os.path.getsize(self.filename) > 0:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)

    def save_caches(self):
        with open(self.filename, 'w') as f:
            json.dump(self.cache, f)

    def extractParams(href):
        str1 = Process.extractQuery(href)
        return {x[0] : x[1] for x in [x.split("=") for x in str1[1:].split(";") ]}

    def extractQuery(href):
        parts = href.split('?')
        return parts[1] if len(parts) > 1 else ''

    def dictToDate(d):
        if 'yg' in d.keys() and 'mg' in d.keys() and 'dg' in d.keys():
            return d['yg'] + '-' + d['mg'].zfill(2) + '-' + d['dg'].zfill(2)
        elif 'yg' in d.keys():
            return d['yg']
        return ''

    def browse(self, url):
        #print('    ', url)
        response = requests.get(url)
        parts = response.text.split('<h3')
        soup = BeautifulSoup(parts[0], "html.parser")
        sex = soup.select('h1 img')[0]['alt'].strip() if len(soup.select('h1 img')) > 0 else ''
        firstname = soup.select('h1 a')[0].text.strip() if len(soup.select('h1 a')) > 0 else ''
        lastname = soup.select('h1 a')[1].text.strip() if len(soup.select('h1 a')) > 1 else ''
        permalink_ = soup.select('h1 input')[0]['value'].strip() if len(soup.select('h1 input')) > 0 else ''
        parts = permalink_.replace('[', '').replace(']', '').split('/')
        permalink = ('p=%s;n=%s;' % (parts[0], parts[1]) + ('oc=%s' % (parts[2],) if parts[2] !='0' else '')) if len(parts) > 2 else ''
        dict1 = Process.extractParams(soup.select('ul li a.date')[0]['href'].strip()) if len(soup.select('ul li a.date')) > 0 else {}
        birthdate = Process.dictToDate(dict1)
        dict2 = Process.extractParams(soup.select('ul li a.date')[1]['href'].strip()) if len(soup.select('ul li a.date')) > 1 else {}
        deathdate = Process.dictToDate(dict2)
        birthplace = soup.select('ul li script')[0].text.strip().split('"')[1] if len(soup.select('ul li script')) > 0 else ''
        deathplace = soup.select('ul li script')[0].text.strip().split('"')[1] if len(soup.select('ul li script')) > 0 else ''
        print(sex, firstname, lastname, permalink, birthdate, deathdate, birthplace, deathplace)
        DB.cur.execute('INSERT INTO people (firstname, lastname, sex, birthdate, birthplace, deathdate, deathplace, permalink) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (firstname, lastname, sex, birthdate, birthplace, deathdate, deathplace, permalink))
        self.cache[url] = True
        DB.con.commit()
        soup = BeautifulSoup(response.text, "html.parser")
        start = soup.find('h3', text='Parents')
        if start:
            ul = start.findNext('ul')
            links = ul.findAll('li')
            parent1 = Process.extractQuery(links[0].find('a')['href'].strip()) if len(links) > 0 else ''
            permalink1 = ''
            if parent1 and Process.base + parent1 not in self.cache.keys():
                permalink1 = self.browse(Process.base + parent1)
            parent2 = Process.extractQuery(links[1].find('a')['href'].strip()) if len(links) > 1 else ''
            permalink2 = ''
            if parent2 and Process.base + parent2 not in self.cache.keys():
                permalink2 = self.browse(Process.base + parent2)
            if permalink1 or permalink2:
                family_id = permalink1 + '#' + permalink2
                DB.cur.execute('INSERT INTO family (id, father_permalink, mother_permalink) VALUES (?, ?, ?)', (family_id, permalink1, permalink2))
                DB.cur.execute('UPDATE people SET family_id = ? WHERE permalink = ?', (family_id, permalink))
        return permalink

if __name__ == '__main__':
    DB.update()
    process = Process('cache.json')
    process.init_caches()
    url = sys.argv[1] if len(sys.argv) > 1 else ''
    if (url):
        process.browse(url)
        DB.con.commit()
        process.save_caches()
    else:
        print('Please provide a URL')
