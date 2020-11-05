from urllib import request
import zlib
import datetime
from pyquery import PyQuery as pq
import math
import logging
import sys
import argparse
import os
import re
import threading
import time
from striprtf.striprtf import rtf_to_text
import queue

version = 1.0
update_needed = False
with request.urlopen('https://raw.githubusercontent.com/JaroDeklerck/bertem_bib_python/main/version') as response:
    new_version = float(response.read().decode('utf-8'))
    if os.path.isfile('version'):
        with open('version', 'r') as f:
            version = float(f.readline())
    else:
        with open('version', 'w') as f:
            f.write(str(new_version))
    print('Local version: {} - Online version: {}'.format(version, new_version))
    if new_version > version:
        print('Newer version found -> Updating')
        update_needed = True
    else:
        print('No update found -> running as normal')
if update_needed:
    with request.urlopen('https://raw.githubusercontent.com/JaroDeklerck/bertem_bib_python/main/downloadArticles.py') as response:
        with open('downloadArticles.py', 'w') as f:
            f.write(response.read().decode('utf-8'))
            print('Updated, rerunning the application')
            os.execv(sys.executable,[sys.executable.split("/")[-1]]+list(map(lambda s: s.replace('"', '\\"'), sys.argv)))


parser = argparse.ArgumentParser(
    description='Download all articles from bib Bertem')
# parser.add_argument('username')
# parser.add_argument('password')
parser.add_argument('search_input',
                    help='Exact same search input as on the website')
parser.add_argument(
    '-d',
    '--directory',
    help='Directory name for the articles (default is search input)',
    default='default_to_be_replaced')

parser.add_argument('-l', '--logging', help='Filename for logging', default='log')

args = parser.parse_args()

if (args.directory == 'default_to_be_replaced'):
    args.directory = args.search_input.replace(',', '_').replace('"', '')

if not os.path.isdir(args.directory):
    os.mkdir(args.directory)


NR_OF_THREADS = 10
exit_flag = False
threads = []
article_queue = queue.Queue(100)

max_articles = 0
max_pages = 0
finished_articles = 0

last_pages = []
last_article_ids = ['']*10
php_sess_id = 's1etia64nfif8dnjebqafod133'
if os.path.isfile('properties'):
    with open('properties', 'r') as f:
        lines = f.readlines()
        for line in lines:
            split_line = line.split('=')
            if len(split_line) == 2:
                if split_line[0] == 'articleIds':
                    last_article_ids = split_line[1][:-1].split(',')
                elif split_line[0] == 'phpSessId':
                    php_sess_id = split_line[1][:-1]

def cleanup():
    global last_article_ids, php_sess_id
    with open('properties', 'w') as f:
        f.writelines(['articleIds={}\n'.format(','.join(last_article_ids)), 'phpSessId={}\n'.format(php_sess_id)])
    print('')

def log(message):
    global args
    with open(args.logging, 'a') as f:
        f.write(message+'\n')

def pageWorker(url, maxPage):
    for i in range(maxPage, -1, -1):
        ids = readSearchPage(url, i)
        for id in ids:
            article_queue.put(id)

pageThread = None

def articleWorker(url, n):
    global last_article_ids, finished_articles, pageThread
    while (pageThread.is_alive() or not article_queue.empty()) and not exit_flag:
        article_id = article_queue.get()
        last_article_ids[n] = article_id
        downloadArticle(article_id)
        finished_articles += 1

def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '\u2588', printEnd = "\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * ((iteration+1) / float(total+1)))
    filledLength = int(length * (iteration+1) // (total+1))
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

def downloadArticle(articleId):
    global args, exit_flag
    if exit_flag:
        return
    url = "https://www.gopress.be/Public/download-article.php?articleOriginalId={}&format=rtf".format(
        articleId)

    headers = {}
    headers[
        'Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
    headers['Accept-Language'] = 'en-US,en;q=0.9,nl;q=0.8,fr;q=0.7'
    headers['Sec-Fetch-Dest'] = 'document'
    headers['Sec-Fetch-Mode'] = 'navigate'
    headers['Sec-Fetch-Site'] = 'none'
    headers[
        'User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4277.0 Safari/537.36 Edg/87.0.658.0'
    headers['Cookie'] = 'PHPSESSID={}'.format(php_sess_id)

    req = request.Request(url, {}, headers)
    with request.urlopen(req) as response:
        text = response.read()
        decoded = text.decode('utf-8')
        if decoded == 'Action not authorized when user not authenticated' :
            print('Not authenticated, please make sure you are logged in and have an arbitrary article open')
            exit_flag = True
            return
        elif decoded.startswith('<html><head><title>Download error</title></head>'):
            log('Following article couldn\'t be downloaded: {}'.format(articleId))
            return
        elif decoded == 'Article not found : Article not found':
            log('Following article couldn\'t be found: {}'.format(articleId))
            return
        filename = buildFilename(rtf_to_text(decoded).split('\n'))
        if filename == 'unknown':
            log('Following article couldn\'t be parsed: {}'.format(articleId))
            return
        path = os.path.join(args.directory, filename)
        if os.path.isfile(path):
            log('Following article was already downloaded: {}'.format(filename))
            return
        with open(path, 'wb') as f:
            f.write(text)
    del req

def handleFoundArticle(query):
    content = query('div.news-archive-item__content')
    hyperlink = content('h2.news-archive-item__title a')
    del content
    href = hyperlink.attr('href')
    del hyperlink
    index_start = href.find('articleOriginalId%3D')
    index_end = href.find("%26language%3D")
    article_id = href[index_start + 20:index_end]
    return article_id

def buildFilename(rtf):
    try:
        if re.match('(.*) - (\d{2} [a-zA-Z]{3}\.? \d{4})', rtf[0]):
            source_date = rtf[0]
            title_index = 2
            if re.match('Page \d+', rtf[1]):
                page = 'p-' + rtf[1][5:]
            else:
                page = 'unknown'
                title_index = 1
            if len(rtf) - 1 >= title_index:
                title_list = re.split('[ -]', rtf[title_index])
                title_text = ' '.join(title_list[:15])
            else:
                title_text = 'unknown'
        elif re.match('(.*) - (\d{2} [a-zA-Z]{3}\.? \d{4})', rtf[1]):
            title_text = ' '.join(re.split('[ -]', rtf[0])[:15])
            source_date = rtf[1]
            if len(rtf) - 1 >= 2 and re.match('Page \d+', rtf[2]):
                page = 'p-' + rtf[2][5:]
            else:
                page = 'unknown'
        source = re.sub('[ /]', '-', source_date.split(' - ')[0]).replace('*', '')
        date = datetime.datetime.strptime(source_date.split(' - ')[-1].replace('.', ''), '%d %b %Y').strftime('%Y%m%d')
        if len(title_text) > 100:
            title_text = title_text[:100]
        chars = re.escape('":?;=+~[]{}<>\u201c\u201d()\u2019*')
        title = re.sub('[{}]'.format(chars), '', re.sub('[ /,.]', '-', title_text))
        if page != 'unknown':
            return '{}_{}_{}_{}.rtf'.format(date, source, page, title)
        else:
            return '{}_{}_{}.rtf'.format(date, source, title)
    except Exception as e:
        print(rtf)
        logging.error('Error', e)
        return 'unknown'

def readSearchPage(url, page):
    query = pq('{}&page={}'.format(url, page))
    results = query('div.news-archive-item')
    del query
    ids = []
    for found in results:
        ids.append(handleFoundArticle(pq(found)))
    del results
    return ids

def getMaxPages(url):
    global max_articles
    page = pq(url)
    result_count = int(
        page('div.catalog-search-result-count h2 strong').text())
    max_articles = result_count
    del page
    return math.floor(result_count / 20)

def pageCheckWorker(url, pages):
    global last_article_ids
    for i in pages:
        if len(last_article_ids) == 0:
            break
        checkPageForArticleIds(url, i)

def checkPageForArticleIds(url, page):
    global last_article_ids, last_pages
    ids = readSearchPage(url, page)
    intersect = set(ids).intersection(set(last_article_ids))
    if len(intersect) > 0:
        last_pages.append(page)
        for i in intersect:
            last_article_ids.remove(i)

def findLastPageNr(url):
    global last_article_ids, threads, max_pages, NR_OF_THREADS, last_pages
    try:
        max_pages = getMaxPages(url)
    except:
        print('No results for the search input')
        raise
    if all(x == '' for x in last_article_ids):
        return
    nr_pages = math.floor(max_pages / NR_OF_THREADS)
    rest = max_pages % NR_OF_THREADS
    for x in range(NR_OF_THREADS):
        pages = list(range(x * nr_pages, (x + 1) * nr_pages))
        if x == NR_OF_THREADS - 1  and rest != 0:
            base = nr_pages * NR_OF_THREADS
            for y in range(1, rest + 1):
                pages.append(base + y)
        t = threading.Thread(target=pageCheckWorker, daemon=True, args=(url, pages,))
        t.start()
        threads.append(t)
    while any(t.is_alive() for t in threads):
        time.sleep(1)
    last_article_ids = ['']*10
    threads = []
    max_pages = max(last_pages)
    
def getArticleList(searchInput):
    global max_pages, pageThread, max_articles, threads, finished_articles
    url = 'https://bertem.bibliotheek.be/krantenarchief?q={}'.format(
        searchInput.replace(',', '%2C'))
    findLastPageNr(url)
    print('Starting from page {}'.format(max_pages))
    pageThread = threading.Thread(target=pageWorker, daemon=True, args=(url, max_pages,))
    pageThread.start()
    for x in range(NR_OF_THREADS):
        t = threading.Thread(target=articleWorker, daemon=True, args=(url, x,))
        t.start()
        threads.append(t)
    while any(t.is_alive() for t in threads):
        printProgressBar(finished_articles, max_articles, prefix=' Progress:', suffix='Complete')
        time.sleep(1)


try:
    getArticleList(args.search_input)
except:
    exit_flag = True
    for t in threads:
        t.join()
    print('\nSomething went wrong')
finally:
    cleanup()
    print('')


