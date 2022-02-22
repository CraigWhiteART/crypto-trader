from datetime import datetime, timedelta
import requests
import pandas as pd
from Util import IsBlackListed
from config import *
import numpy as np
import pickle
import talib
from config import *
from Bot import Bot
from Backtest import Backtest
import json

client = Client(API, SECRET)
tickers = client.get_ticker()
tickers = list(filter(lambda ticker: ticker['symbol'].endswith('USDT'), tickers))
tickers = list(filter(lambda t: not IsBlackListed(t['symbol']), tickers))
tickers = [symbol for symbol in sorted(tickers, key=lambda item: -abs(float(item['priceChangePercent'])))]
tickers = tickers[:50]

all_symbols = ['LUNA', 'SAND', 'MATIC', 'NEO', 'GALA', 'BETA', 'TRX', 'AAVE']
for ticker in tickers:
    symbol = ticker['symbol'].replace('USDT', '')
    if symbol not in all_symbols:
        all_symbols.append(symbol)

start_date = datetime.utcnow() - timedelta(days=2)
end_date = datetime.utcnow() - (timedelta(minutes=30))

results = {}
for symbol in all_symbols:
    try:
        bot = Backtest(client, [symbol], start_date, end_date)
        bot.run()
        equity = bot.GetEquity()
        if equity > bot.initial_balance:
            results[symbol] = bot.average_profit
    except:
        continue

results = {symbol: equity for symbol, equity in sorted(results.items(), key=lambda item: -item[1])}
with open('best_tokens.json', 'w') as outfile:
    json.dump(results, outfile)

# import cProfile
# cProfile.run('bot.run()')


# plt.plot(df['Open Time'], df['Close'])
# # plt.plot(df['Open Time'],ema8)
# # plt.plot(df['Open Time'],ema13)
# # plt.plot(df['Open Time'],ema21)
# # plt.plot(df['Open Time'],ema34)
# # plt.plot(df['Open Time'],ema55)

# longs = df[df['Decision'] == 'Long']
# exits = df[df['Decision'] == 'Exit Long']


# plt.scatter(longs['Open Time'], longs['Close'], marker='^', c='#00ff00')
# plt.scatter(exits['Open Time'], exits['Close'],marker='v',c='#ff0000')

# plt.xticks(rotation = 20)
# plt.show()
