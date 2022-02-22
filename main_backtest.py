from datetime import datetime, timedelta
import requests
import pandas as pd
from config import *
import numpy as np
import pickle
import talib
from config import *
from Bot import Bot
from Backtest import Backtest
import json

client = Client(API, SECRET)

start_date = pd.Timestamp(2022, 1, 1, 0, 0, 0)
end_date = pd.Timestamp(2022, 1, 31, 0, 0, 0)

# start_date = datetime.utcnow() - timedelta(days=2)
# end_date = datetime.utcnow() - timedelta(minutes=30)
# start_date = pd.Timestamp(2022, 2, 16, 0, 0, 0)
# end_date = pd.Timestamp(2022, 2, 22, 0, 0, 0)

all_symbols = ['LUNA']
# with open('best_tokens.json') as json_file:
#     best_tokens = json.load(json_file)
#     all_symbols = list(best_tokens.keys())[:5]

daysToTest = 4
bot = Backtest(client, all_symbols, start_date, end_date)
bot.run()

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
