import json
import os
from pathlib import Path
import platform
import dateparser
import pytz
from datetime import datetime
import pandas as pd
import numpy as np
import math
import pickle

import pytz
pd.options.mode.chained_assignment = None 

def binanceToPandas(klines):
    klines = np.array(klines) #reverse the data
    df = pd.DataFrame(klines.reshape(-1, 12), dtype=float, columns=('Open Time',
                                                                    'Open',
                                                                    'High',
                                                                    'Low',
                                                                    'Close',
                                                                    'Volume',
                                                                    'Close time',
                                                                    'Quote asset volume',
                                                                    'Number of trades',
                                                                    'Taker buy base asset volume',
                                                                    'Taker buy quote asset volume',
                                                                    'Ignore'))
    df['Open Time'] = pd.to_datetime(df['Open Time'], unit='ms')
    return df


def truncate(number, digits) -> float:
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


def savePickle(var, file_name):
    outfile = open(file_name, 'wb')
    pickle.dump(var, outfile)

    outfile.close()


def openPickle(file_name):
    outfile = open(file_name, 'rb')
    df = pickle.load(outfile)

    outfile.close()

    return df


def HA(df):
    # HA_OPEN = 'HA_Open'
    # HA_HIGH = 'HA_High'
    # HA_LOW = 'HA_Low'
    # HA_CLOSE = 'HA_Close'
    
    df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4

    # open_data = [0] * len(df)
    # for i in range(0, len(df)):
    #     if i == 0:
    #         open_data[i] = (df['Open'].iat[i] + df['Close'].iat[i]) / 2
    #     else:
    #         open_data[i] = (open_data[i - 1] + open_data[i - 1]) / 2
    # df['HA_Open'] = open_data
            
    # df['HA_High'] = df[['HA_Open', 'HA_Close', 'High']].max(axis=1)
    # df['HA_Low'] = df[['HA_Open', 'HA_Close', 'Low']].min(axis=1)

    return df

def Crossover(x, y):
    return x.iloc[-1] > y.iloc[-1] and x.iloc[-2] < y.iloc[-2]
    
def Crossunder(x, y):
    return x.iloc[-1] < y.iloc[-1] and x.iloc[-2] > y.iloc[-2]

def date_to_milliseconds(date):
    if date is None:
        return None
    """Convert UTC date to milliseconds
    If using offset strings add "UTC" to date string e.g. "now UTC", "11 hours ago UTC"
    See dateparse docs for formats http://dateparser.readthedocs.io/en/latest/
    :param date_str: date in readable format, i.e. "January 01, 2018", "11 hours ago UTC", "now UTC"
    :type date_str: str
    """
    # get epoch value in UTC
    epoch = datetime.utcfromtimestamp(0).replace(tzinfo=pytz.utc)
    # parse our date string
    d = date
    # if the date is not timezone aware apply UTC timezone
    if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
        d = d.replace(tzinfo=pytz.utc)

    # return the difference in time
    return int((d - epoch).total_seconds() * 1000.0)

def file_modified_date(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See http://stackoverflow.com/a/39501288/1709587 for explanation.
    """
    if platform.system() == 'Windows':
        return os.path.getmtime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        return stat.st_mtime

blacklist = None
blacklistFile = './blacklist.json'
def BlacklistCoin(coin):
    global blacklist
    LoadBlacklist()
    blacklist.append(coin)
    with open(blacklistFile, 'w') as outfile:
        json.dump(blacklist, outfile)
def LoadBlacklist():
    global blacklist
    if blacklist is None:
        blacklist = []
    if not os.path.isfile(blacklistFile):
        return
    with open(blacklistFile) as json_file:
        blacklist = json.load(json_file)

def IsBlackListed(coin):
    global blacklist
    if blacklist is None:
        LoadBlacklist()
    if coin.endswith("DOWNUSDT") or coin.endswith("UPUSDT"):
        return True
    return coin in blacklist
