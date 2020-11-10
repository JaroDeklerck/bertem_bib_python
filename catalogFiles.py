import argparse
import os
import datetime
import pathlib
import sys
import pandas

parser = argparse.ArgumentParser(description='Catalog a folder into excel')
parser.add_argument('file', help='Excel filename')
parser.add_argument(
    '-d',
    '--directory',
    help='Directory name for the articles (default is search input)',
    default='default_to_be_replaced')

parser.add_argument('-l',
                    '--logging',
                    help='Filename for logging',
                    default='catalog.log')

args = parser.parse_args()

wdir = os.path.join(pathlib.Path().absolute(),
                    args.directory)

if not args.file.endswith('.xlsx'):
    filename = args.file.split('.')[0] + '.xlsx'
else:
    filename = args.file

def log(message):
    global args
    with open(args.logging, 'a', encoding='utf-8') as f:
        f.write(message + '\n')

headers = [
        'Titel', 'Bron', 'Datum gepubliceerd', 'Datum gedownload',
        'Datum laatst aangepast', 'Pad', 'Link'
    ]
if os.path.isfile(filename):
    df = pandas.read_excel(filename, sheet_name='Catalog', index_col=0, dtype=dict.fromkeys(headers, 'object'))
    for i in df.index:
        df.at[i, 'Link'] = '=HYPERLINK("{}", "Ga naar bestand")'.format(df.at[i, 'Pad'])
else:
    df = pandas.DataFrame(dict.fromkeys(headers, []))

def cleanup():
    global filename, df
    with pandas.ExcelWriter(filename) as writer:
        df.to_excel(writer, sheet_name='Catalog')

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

def isFileInCatalog(path):
    global df
    if len(df['Pad'].values) == 0:
        return False
    return len(df['Pad'].str.contains(path, na=False, regex=False)) > 0


def parseFileEntry(entry):
    if entry.is_dir():
        return None
    dict1 = {}
    name = entry.name.split('.')[0]
    split_name = name.split('_')
    try:
        if len(split_name) < 3:
            raise Exception()
        dict1[headers[0]] = split_name[-1].replace('-', ' ').strip()
        dict1[headers[1]] = split_name[1].replace('-', ' ').strip()
        dict1[headers[2]] = datetime.datetime.strptime(split_name[0], '%Y%m%d').strftime('%d/%m/%Y')
    except:
        dict1 = {headers[0]: name, headers[1]: '', headers[2]: ''}
    stats = entry.stat()
    dict1[headers[3]] = datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%d/%m/%Y')
    dict1[headers[4]] = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%d/%m/%Y')
    dict1[headers[5]] = entry.path
    dict1[headers[6]] = '=HYPERLINK("{}", "Ga naar bestand")'.format(entry.path)
    return dict1


def handleFiles():
    global wdir, df
    nr_of_files = len(os.listdir(wdir))
    printProgressBar(0, nr_of_files, prefix=' Progress:', suffix='Complete')
    x = 0
    rows_list = []
    for entry in os.scandir(wdir):
        if not isFileInCatalog(entry.path):
            rows_list.append(parseFileEntry(entry))
        else:
            log('File already in catalog: {}'.format(entry.path))
        x += 1
        printProgressBar(x, nr_of_files, prefix=' Progress:', suffix='Complete')
    new_frame = pandas.DataFrame(rows_list)
    df = df.append(new_frame)

try:
    handleFiles()
except Exception as e:
    print('\nSomething went wrong')
finally:
    cleanup()