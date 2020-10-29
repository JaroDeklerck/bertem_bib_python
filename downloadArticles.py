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
import iptcinfo3

logging.getLogger('iptcinfo').setLevel(logging.ERROR)

version = 1.1
update_needed = False
with request.urlopen('https://raw.githubusercontent.com/JaroDeklerck/bertem_bib_python/main/version') as response:
    new_version = float(response.read().decode('utf-8'))
    print('Local version: {} - Online version: {}'.format(version, new_version))
    if new_version > version:
        print('Newer version found -> Updating')
        update_needed = True
if update_needed:
    with request.urlopen('https://raw.githubusercontent.com/JaroDeklerck/bertem_bib_python/main/downloadArticles.py') as response:
        with open('downloadArticles.py', 'w') as f:
            f.write(response.read().decode('cp347'))
            print('Updated, please rerun the application')


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
parser.add_argument(
    '-f',
    '--force-check',
    help=
    'Go over every article (default is until most recent downloaded article',
    action='store_true')
parser.add_argument('-F',
                    '--force-all',
                    help='Overwrite every article',
                    action='store_true')

args = parser.parse_args()

if (args.directory == 'default_to_be_replaced'):
    args.directory = args.search_input.replace(',', '_').replace('"', '')

if not os.path.isdir(args.directory):
    os.mkdir(args.directory)

exit_flag = False
threads = []

max_pages = 0
finished_pages = 0

class myThread (threading.Thread):
   def __init__(self, threadID, name, counter, function, functionArgs):
      threading.Thread.__init__(self)
      self.threadID = threadID
      self.name = name
      self.counter = counter
      self.function = function
      self.functionArgs = functionArgs
      threads.append(self)
   def run(self):
      global max_pages, finished_pages, exit_flag
      if exit_flag:
          return
      self.function(self.functionArgs[0], self.functionArgs[1])
      threads.remove(self)
      finished_pages += 1
      printProgressBar(finished_pages, max_pages, prefix=' Progress:', suffix='Complete')

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
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = printEnd)
    # Print New Line on Complete
    if iteration == total: 
        print()

def downloadArticlePdf(articleId):
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
    headers['Cookie'] = 'PHPSESSID=s1etia64nfif8dnjebqafod133'

    req = request.Request(url, {}, headers)
    with request.urlopen(req) as response:
        text = response.read()
        decoded = text.decode('utf-8')
        if decoded == 'Action not authorized when user not authenticated' :
            print('Not authenticated, please make sure you are logged in and have an arbitrary article open')
            exit_flag = True
            return
        if decoded.startswith('<html><head><title>Download error</title></head>') or decoded == 'Article not found : Article not found':
            return
        filename = buildFilename(rtf_to_text(decoded).split('\n'))
        if filename == 'unknown':
            exit_flag = True
            return
        exists = checkDownloadedArticles(articleId)
        if (not args.force_all and not args.force_check and exists):
            exit_flag = True
        elif (args.force_all or not exists):
            path = os.path.join(args.directory, filename)
            with open(path, 'wb') as f:
                f.write(text)
            info = iptcinfo3.IPTCInfo(path)
            info['keywords'] = [articleId]
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


def checkDownloadedArticles(articleId):
    global args
    for f in os.listdir(args.directory):
        info = iptcinfo3.IPTCInfo(os.path.join(args.directory, f))
        if articleId in info['keywords']:
            return True 


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
                # end_index = [i for i, word in enumerate(title_list) if re.match('^[a-zA-Z][a-z]+[A-Z0-9][a-zA-Z0-9]*$', word) or word == '-']
                # if len(end_index) > 0:
                #     print(title_list[end_index[0]])
                #     if title_list[end_index[0]] != '-':
                #         title_list[end_index[0]] = re.findall('[A-Z][^A-Z]*', title_list[end_index[0]])[0]
                #     title_text = ' '.join(title_list[:end_index[0]])
                #     print(title_text)
                # else:
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
        chars = re.escape('":?.;=+~[]{}<>“”*()‘')
        title = re.sub('[{}]'.format(chars), '', re.sub('[ /]', '-', title_text))
        if page != 'unknown':
            return '{}_{}_{}_{}.rtf'.format(date, source, page, title)
        else:
            return '{}_{}_{}.rtf'.format(date, source, title)
    except Exception as e:
        print(rtf)
        logging.error('Error', e)
        return 'unknown'


def readSearchPage(url, page):
    global args
    global exit_flag
    query = pq('{}&page={}'.format(url, page))
    results = query('div.news-archive-item')
    del query
    for found in results:
        article_id = handleFoundArticle(pq(found))
        try:
            downloadArticlePdf(article_id)
        except Exception as e:
            logging.error('Error', exc_info=e)
            exit_flag = True
    del results


def getMaxPages(url):
    page = pq(url)
    result_count = int(
        page('div.catalog-search-result-count h2 strong').text())
    del page
    return math.floor(result_count / 20)


def getArticleList(searchInput):
    global exit_flag
    global max_pages
    url = 'https://bertem.bibliotheek.be/krantenarchief?q={}'.format(
        searchInput.replace(',', '%2C'))
    try:
        max_pages = getMaxPages(url)
    except:
        print('No results for the search input')
        return
    for x in range(max_pages + 1):
        while threads.__len__() >= 10:
            time.sleep(0.5)
        if not exit_flag:
            t = myThread(x, 'Page {}'.format(x), x, readSearchPage, (url, x))
            t.start()
        else:
            print('\nStopped early')
            break



getArticleList(args.search_input)
print('')