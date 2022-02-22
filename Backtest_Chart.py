from collections import defaultdict
from operator import eq
import os
from sqlite3 import Timestamp
from config import API, SECRET, markets, tick_interval
from binance.client import Client
import pandas as pd
import numpy as np
from Util import *
from time import sleep
from Strategy import calculateIndicators, strategyDecision
import math
from datetime import datetime, timedelta

from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA


def getKlines(client, symbol, interval, start_time, end_time):
    df = None
    key = f'{symbol}-{interval}-' + str(start_time).replace(':', '.').replace('/', '-') + " - " + str(end_time).replace(':', '.').replace('/', '-')
    fname = './cache/' + key + '.pickle'
    try:
        if os.path.isfile(fname):
            df = openPickle(fname)
    except Exception as ex:
        print(ex)
    if df is None:
        print(f"Getting klines {key}")
        start_time_str = date_to_milliseconds(start_time) #.strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = date_to_milliseconds(end_time) #.strftime("%Y-%m-%d %H:%M:%S")
        raw_klines = client.get_historical_klines(
            symbol=symbol, interval=interval, start_str = start_time_str, end_str = end_time_str )
        df = binanceToPandas(raw_klines)
        df = df.set_index('Open Time', drop=False)
        df = HA(df)

        if interval is not Client.KLINE_INTERVAL_15MINUTE:
            df = df.resample('15min').ffill()
            idx = pd.date_range(df.index.min(), Timestamp(end_time.year, end_time.month, end_time.day, end_time.hour, end_time.minute), freq="15min")
            df = df.reindex(idx, method='ffill')
            df['Open Time'] = df.index
        
        savePickle(df, fname)

    return df

def EXACT(arr: pd.Series, n: int) -> pd.Series:
    return pd.Series(arr).rolling(n).max()

class HA_4H_Cross(Strategy):
    n1 = 1
    openPeriod = 10
    closePeriod = 10

    def init(self):
        self.sma4H = self.I(EXACT, self.data.HA_Close4H, self.n1)
        self.smaOpen = self.I(SMA, self.data.HA_Close, self.openPeriod)
        self.smaClose = self.I(SMA, self.data.HA_Close, self.closePeriod)

    def next(self):
        if crossover(self.sma4H, self.smaOpen):
            self.buy()
        elif crossover(self.smaClose, self.sma4H):
            self.position.close()



client = Client(API, SECRET)

symbol = "LUNAUSDT"
start_date = Timestamp(2022, 1, 1, 0, 0, 0)
end_date = Timestamp(2022, 2, 19, 0, 0, 0)

klines = getKlines(client, symbol, tick_interval, start_date, end_date)
kline4H = getKlines(client, symbol, Client.KLINE_INTERVAL_4HOUR, start_date, end_date)
kline4H = kline4H.drop(columns=['Open','High','Low','Close','Volume','Close time','Quote asset volume','Number of trades','Taker buy base asset volume','Taker buy quote asset volume','Ignore'])
kline4H.rename(columns={'HA_Close':'HA_Close4H'}, inplace=True)

klines = klines.join(kline4H, rsuffix="4H")

bt = Backtest(klines, HA_4H_Cross,
              cash=400, commission=.002,
              exclusive_orders=True)
output = bt.optimize(openPeriod=list(range(5,30, 2)), closePeriod=list(range(5,30, 2)),return_heatmap=True, maximize='Equity Final [$]')
# output = bt.run()
bt.plot(open_browser=False)
print(output)