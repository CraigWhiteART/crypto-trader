from http import client
import imp
import json
import time
from xmlrpc.client import DateTime
from config import API, SECRET, markets, tick_interval
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import numpy as np
from Util import *
from time import sleep
from Strategy import calculateIndicators, strategyDecision
import math
from datetime import datetime, timedelta


class Bot:
    def __init__(self):
        self.queuedMessages = []
        self.tokens_file_date = None
        self.lastSentEquity = datetime.min

        print("- Initializing Bot...")
        self.client = Client(API, SECRET)
        # self.printPush("- Loaded API keys")

        self.margin_per_entry = 0.6
        self.goal_entry = 100

        self.usdt = 0
        self.position_val = 0
        self.balance = []
        self.positions = {}
        self.closed_positions = {}
        self.precision = {}
        self.available_currencies = []
        self.cur_price = {}
        self.LoadMarkets()
        self.generateBoughtStatus()
        # print('- Done fetching balance')
        self.printPush(f'Balance: {self.usdt:.2f} USDT')
        # self.printPush(f'Equity: {self.GetEquity():.2f} USDT')

    def run(self):
        self.printPush("- Bot is running")
        self.printPush(str(self.markets))
        print('\n--------TRADES-------\n')
        self.clearPush()
        passes = -1
        while True:                
            try:
                passes += 1
                minuteCorrect = datetime.utcnow().minute in {0, 15, 30, 45}
                if minuteCorrect or passes == 0:
                    entry_minute = int(math.floor(datetime.utcnow().minute / 15.0) * 15)
                    for symbol in self.markets:
                        symbol = symbol + 'USDT'
                        klines = kline4H = None
                        end_time = datetime.utcnow()
                        end_time = end_time.replace(minute=entry_minute, second=0, microsecond=0) - timedelta(seconds=1)
                        klines = self.getKlines(symbol, tick_interval, 40, end_time)
                        kline4H = self.getKlines(symbol, Client.KLINE_INTERVAL_4HOUR, 2, end_time)
                            
                        price = klines["Close"].iloc[-1]
                        self.cur_price[symbol] = price

                        if not minuteCorrect:
                            continue

                        # klines = klines[:-1]#delete live data elements
                        # kline4H = kline4H[:-1]

                        # fma, sma = calculateIndicators(klines, kline4H)

                        #self.printPush("{0}\t fma: {1}\t sma: {2}".format(symbol, fma.iloc[-1], sma.iloc[-1]))
                        enterLong, exitLong = calculateIndicators(klines, kline4H)

                        pyramid = False
                        if self.CanCreatePositions() and not exitLong and self.positions[symbol] and len(self.positions[symbol]) == 1:
                            lastEntryPrice = self.GetLatestPositionPrice(symbol)
                            pyramid = klines['Close'].iloc[-1] < lastEntryPrice * 0.99
                            enterLong |= pyramid

                        if self.positions[symbol]:
                            if exitLong:
                                self.sell(symbol, klines)
                            elif pyramid:
                                self.printPush("Lets Pyramid {symbol}")
                                self.buy(symbol, klines)
                        else:
                            if enterLong:
                                self.buy(symbol, klines)

                #send report on the hour datetime.utcnow().minute == 0
                if (datetime.now() - self.lastSentEquity).total_seconds() > 7200:
                    self.printPush(f'Equity: {self.GetEquity():.2f} USDT')
                    self.lastSentEquity = datetime.now()

                self.PushQueuedAsOne()
                self.LoadMarkets()
                sleeptime = 60 - datetime.utcnow().second
                sleep(sleeptime + 5)
            except Exception as ex: 
                self.lastSentEquity = datetime.min
                print(ex) 
                self.queuePush(str(ex))
                sleep(10)

    def PrintProfitReport(self):
        for symbol in self.closed_positions.keys():
            closed_positions = self.closed_positions[symbol]
            if len(closed_positions) == 0:
                self.printPush(f'{symbol}\tNo Positions Taken')
                continue
            # 'percent': percent,
            # 'profit': net,
            # 'qty': amount,
            # 'price': price,
            # 'volume': usdtWorth,
            # 'time_elapsed': time_elapsed, 
            total_profit = sum(float(p['profit']) for p in closed_positions)
            biggest_profit = max(float(p['profit']) for p in closed_positions)
            avg_hold_hours = 0 # (sum(p['time_elapsed'].seconds for p in closed_positions) / len(closed_positions)) / 3600.0
            avg_profit = total_profit / len(closed_positions)
            percent_of_profits = (total_profit / net) * 100.0
            self.printPush(f'{symbol: <9}\tTotal Gains: {total_profit:.2f}\tAvg Gains: {avg_profit:.2f}\tBiggest Gain: {biggest_profit:.2f}\tPercent of Gains: {percent_of_profits:.2f}%\tAvg Hold: {avg_hold_hours:0.2f}hrs')

    def GetLatestPositionPrice(self, symbol):
        positions = self.positions[symbol]
        if positions == None:
            return None
        price = float(positions[len(positions) - 1]['cummulativeQuoteQty'])
        qty = float(positions[len(positions) - 1]['executedQty'])
        return price / qty
        
    def GetTotalUsdtPositionsOfSymbol(self, coin):
        positions = self.positions[coin]
        if positions == None:
            return 0
        return sum(float(order['cummulativeQuoteQty']) for order in positions)

    def generateBoughtStatus(self):
        print('- Generating bought/sold statuses...')
        for coin in self.markets:
            self.generateBoughtStatusForCoin(coin)

    def generateBoughtStatusForCoin(self, coin):
            coin += 'USDT'
            symbol_orders = self.client.get_all_orders(symbol=coin)
            self.closed_positions[coin] = []
            buyOrders = []
            
            price = self.getKlines(coin, tick_interval, 1)["Open"][0]
            qty = self.getSymbolBalance(coin)
            accountedQty = 0
            for o in symbol_orders:
                if o['side'] == 'BUY' and o['status'] == 'FILLED':
                    accountedQty += float(o['executedQty'])
                    buyOrders.append(o)
                else:
                    break

            if len(buyOrders) > 0 and abs((qty - accountedQty) * price) < 5:
                missingQty = qty - accountedQty
                if missingQty > 0:
                    buyOrders[0]['executedQty'] = float(buyOrders[0]['executedQty']) + missingQty
                self.positions[coin] = buyOrders
                self.printPush(f'- {coin} is currently holding ' + str(round(self.GetTotalUsdtPositionsOfSymbol(coin), 2)) + "USDT worth")
                
            else:
                self.positions[coin] = None
                usdt = price * qty
                if (usdt > 1):
                    self.positions[coin] = []
                    self.positions[coin].append({'cummulativeQuoteQty': usdt, 'executedQty': qty});
                    self.printPush(f'- {coin} already holding ' + str(round(self.GetTotalUsdtPositionsOfSymbol(coin), 2)) + "USDT worth")
                

    def CanCreatePositions(self):
        return self.usdt > 10

    def buy(self, symbol, df):
        self.refreshBalance()

        if self.CanCreatePositions():

            price = df["Close"].iloc[-1]

            usdtWorth = max(self.goal_entry, self.usdt * self.margin_per_entry)
            if (usdtWorth < 10):
                usdtWorth = 10
            if(usdtWorth > self.usdt):
                 usdtWorth = self.usdt
            usdtWorth = truncate(usdtWorth, self.precision[symbol])

            amount = usdtWorth/price
            amount = truncate(amount, self.precision[symbol])
            
            coin = symbol.replace("USDT", "")
            try:
                self.printPush(f'{self.TimestampUTC()} UTC: BUY\t{coin: <5} @ {price}/ea\t× {amount}\t(${usdtWorth:.2f})')
                buy_market = self.client.order_market_buy(symbol=symbol, quoteOrderQty=usdtWorth)
            except BinanceAPIException as apiErr:
                if apiErr.code == -1013:
                    BlacklistCoin(symbol.replace('USDT', ''))
                raise apiErr
            
            self.usdt -= usdtWorth
            if self.positions[symbol] == None:
                self.positions[symbol] = []
            self.positions[symbol].append(buy_market)

            self.lastSentEquity = datetime.min
            
            self.LoadMarkets()
            self.refreshBalance()
        else:
            if not any(self.positions.values()):
                print(f"{symbol} | Not enough USDT to trade (minimum of $10)")

    def getSymbolBalance(self, symbol):
        symbol_balance = 0
        for s in self.balance:
            if s['asset'] + 'USDT' == symbol:
                symbol_balance = s['free']
        return symbol_balance

    def sell(self, symbol, df):
        self.refreshBalance()

        symbol_balance = self.getSymbolBalance(symbol)

        price = df["Close"].iloc[-1]

        if symbol_balance * price > 10:

            amount = truncate(symbol_balance, self.precision[symbol])
            usdtWorth = amount * price

            coin = symbol.replace("USDT", "")
            self.printPush(f'{self.TimestampUTC()} UTC: SELL\t{coin: <5} @ {price}/ea\t× {amount}\t(${usdtWorth:.2f})')
            sell_market = self.client.order_market_sell(symbol=symbol, quantity=amount)


            usdtOpen = 0
            for position in self.positions[symbol]:
                usdtOpen += float(position['cummulativeQuoteQty'])
            usdtClose = float(sell_market['cummulativeQuoteQty'])
            net = usdtClose - usdtOpen
            percent = ((usdtClose / usdtOpen) - 1) * 100

            # time_elapsed = 0; sell_market['time'] - self.positions[symbol][0]['time']
            self.usdt += usdtClose
            self.positions[symbol] = None
            
            self.closed_positions[symbol].append({
                'symbol': symbol,
                'percent': percent,
                'profit': net,
                'qty': amount,
                'price': price,
                'volume': usdtWorth,
                # 'time_elapsed': time_elapsed, 
            })

            self.printPush(f'\tP/L: {net:.2f} USDT {percent:.2f}%')
            self.lastSentEquity = datetime.min

        else:
            if not any(self.positions.values()):
                print(f"Not enough {symbol} to trade (minimum of $10)")

    def GetEquity(self):
        equity = self.usdt
        for symbol in self.positions.keys():
            if self.positions[symbol] is None:
                continue
            for position in self.positions[symbol]:
                equity += float(position['executedQty']) * self.cur_price[symbol]
        return equity

    def Timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    def TimestampUTC(self):
        return datetime.utcnow().strftime("%H:%M:%S")

    def getSymbolPrecision(self, symbol):
        symbol_info = None
        fname = f'./symbol_data/{symbol}.symbol_info'
        try:
            if os.path.isfile(fname):
                symbol_info = openPickle(fname)
        except:
            print('Failed to load ' + fname)
        if symbol_info is None:
            symbol_info = self.client.get_symbol_info(symbol=symbol)
            savePickle(symbol_info, fname)

        if 'MARKET' not in symbol_info['orderTypes']:
            self.markets.remove(symbol.replace('USDT'))
        for filt in symbol_info['filters']:
            if filt['filterType'] == 'LOT_SIZE':
                diff = filt['stepSize'].find('1') - filt['stepSize'].find('.')
                self.precision[symbol] = max(diff, 0)
                break

    def getKlines(self, symbol, interval, limit=500, end_date=None):
        df = self.client.get_klines(
            symbol=symbol, interval=interval, limit=limit, endTime=date_to_milliseconds(end_date))
        df = binanceToPandas(df)
        df = df.set_index('Open Time', drop=False)
        df = HA(df)

        if interval is not Client.KLINE_INTERVAL_15MINUTE:
            df = df.resample('15min').ffill()
            if end_date is None:
                end_date = df.index[-1]
            idx = pd.date_range(df.index.min(), end_date, freq="15min")
            df = df.reindex(idx, method='ffill')
            df['Open Time'] = df.index

        return df

    def LoadMarkets(self):
        fname = 'best_tokens.json'
        file_mod_date = file_modified_date(fname)
        if file_mod_date == self.tokens_file_date and len(self.markets) >= 5:
            return
        self.printPush("Loading Best Tokens")
        self.tokens_file_date = file_mod_date
        try:
            with open(fname) as json_file:
                best_tokens = json.load(json_file)
                best_tokens = list(filter(lambda x: not IsBlackListed(x), list(best_tokens.keys()))) 
                self.markets = best_tokens[:5]
        except:
            self.markets = markets
            print("Failed to load best tokens")
        for coin in self.markets:
            if (coin + "USDT") not in self.precision:
                self.getSymbolPrecision(coin + "USDT")
                self.generateBoughtStatusForCoin(coin)

        self.refreshBalance()
            
    def refreshBalance(self):
        balance = self.client.get_account()["balances"]
        if balance is not None:
            self.available_currencies = []
            self.balance = []
            for dict in balance:
                dict["free"] = float(dict["free"])
                dict["locked"] = float(dict["locked"])

                if dict['asset'] == 'USDT':
                    self.usdt = float(dict["free"])
                elif (dict["free"] > 0.0):
                    dict["asset"] = dict["asset"]
                    self.available_currencies.append(dict["asset"])
                    self.balance.append(dict)
                    symbol = dict['asset'] + "USDT"
                    if dict['asset'] not in self.markets:
                        if symbol not in self.cur_price:
                            self.cur_price[symbol] = float(self.client.get_avg_price(symbol=symbol)['price'])
                        price = self.cur_price[symbol]
                        if price * float(dict["free"]) > 10:
                            self.markets.append(dict['asset'])

    def printPush(self, text):
        print(text)
        self.queuePush(text)

    def clearPush(self):
        self.queuedMessages.clear()

    def queuePush(self, text):
        # text = text.replace(': Equity:', ':\nEquity:')
        self.queuedMessages.append(text)

    def PushQueuedAsOne(self):
        self.Push("\r\n".join(self.queuedMessages))
        self.queuedMessages.clear()

    def PushQueued(self):
        while self.queuedMessages:
            self.Push(self.queuedMessages.pop(0))
        
    def Push(self, text):
        import http.client, urllib
        conn = http.client.HTTPSConnection("api.pushover.net:443")
        conn.request("POST", "/1/messages.json",
        urllib.parse.urlencode({
            "token": "aviz5y3xc2hw4fkk21rcpweawz1wf5",
            "user": "ufkn7973ymqnpavjh4ra3qhupjs9xv",
            "message": text
        }), { "Content-type": "application/x-www-form-urlencoded" })
        conn.getresponse()