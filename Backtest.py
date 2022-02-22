from collections import defaultdict
from operator import eq
import os
from sqlite3 import Timestamp
from config import API, SECRET, tick_interval
from binance.client import Client
import pandas as pd
import numpy as np
from Util import *
from time import sleep
from Strategy import calculateIndicators, strategyDecision
import math
from datetime import datetime, timedelta


class Backtest:
    def __init__(self, client, markets, start_date, end_date):
        self.queuedMessages = []
        self.printPush("Initializing Bot...")
        self.client = client

        self.initial_balance    = 500
        self.usdt               = 500
        self.interval = timedelta(minutes=15)
        self.margin_per_entry = 0.6
        self.goal_entry = 100
        self.markets = markets
        # self.markets = [ 'LUNA' ]
        
        # self.start_date = Timestamp(2022, 1, 1, 0, 0, 0)
        # self.end_date = Timestamp(2022, 2, 19, 0, 0, 0)
        self.start_date = start_date # datetime.utcnow() - timedelta(days=daysToTest)
        self.end_date = end_date # datetime.utcnow() - (self.interval * 2)
        self.start_date = self.start_date.replace(minute= math.floor(self.start_date.minute / 15.0) * 15, second=0, microsecond=0)
        self.end_date = self.end_date.replace(minute= math.floor(self.end_date.minute / 15.0) * 15, second=0, microsecond=0)

        self.cur_time = self.start_date

        self.klines_cache = {}


        self.average_profit = 0
        self.position_val = 0
        self.balance = []
        self.positions = {}
        self.closed_positions = {}
        self.precision = {}
        self.available_currencies = []
        self.cur_price = {}
        self.generateBoughtStatus()
        self.generateTicks()
        self.printPush(f'Balance: {self.usdt:.2f} USDT')

    def run(self):
        self.printPush("- Backtest Starting -")
        self.printPush(str(self.markets))
        print('\n--------TRADES-------\n')
        self.PushQueuedAsOne()
        start_test = datetime.now()

        while self.cur_time < self.end_date:
            try:
                for symbol in self.markets:
                    symbol = symbol + 'USDT'
                    klines = self.getKlines(symbol, tick_interval, 40)
                    if len(klines) == 0:
                        continue
                    kline4H = self.getKlines(symbol, Client.KLINE_INTERVAL_4HOUR, 2)
                    if len(kline4H) == 0:
                        continue
                    price = klines["Close"].iloc[-1]
                    self.cur_price[symbol] = price

                    # fma, sma = calculateIndicators(klines, kline4H)

                    #self.printPush("{0}\t fma: {1}\t sma: {2}".format(symbol, fma.iloc[-1], sma.iloc[-1]))
                    enterLong, exitLong = calculateIndicators(klines, kline4H)

                    pyramid = False
                    # if self.CanCreatePositions() and not exitLong and self.positions[symbol] and len(self.positions[symbol]) == 1:
                    #     lastEntryPrice = self.GetLatestPositionPrice(symbol)
                    #     pyramid = klines['Close'].iloc[-1] < lastEntryPrice * 0.99
                    #     enterLong |= pyramid

                    if self.positions[symbol]:
                        if exitLong:
                            self.sell(symbol, klines)
                        elif pyramid:
                            self.printPush(f"Lets Pyramid {symbol}")
                            self.buy(symbol, klines)
                    else:
                        if enterLong:
                            self.buy(symbol, klines)

                self.PushQueuedAsOne()
            except Exception as ex:
                print(ex) 
                self.queuePush(str(ex))
            self.cur_time += self.interval

        self.printPush(f'\n{self.Timestamp()}\n--- Backtest Finished ---')
        self.printPush(f'Backtest took {datetime.now() - start_test}')
        self.PrintProfitReport()

    def PrintProfitReport(self):
        equity = self.GetEquity()

        self.printPush(str(self.markets))
        self.printPush(f'${self.initial_balance} -> ${equity}')
        self.printPush(f'{self.start_date} -> {self.end_date}')
        self.printPush(f'Margin Per Entry: {self.margin_per_entry}\tGoal Entry: {self.goal_entry}')
        
        net = equity - self.initial_balance
        percent = ((equity / self.initial_balance) - 1) * 100

        # self.average_profit = net / len(self.closed_positions)
        self.average_profit = 0
        for closed_positions in self.closed_positions.values():
            sorted_positions = [position for position in sorted(closed_positions, key=lambda item: item['profit'])]
            sorted_positions = sorted_positions[int(max(1, len(sorted_positions)/10)):-int(max(1, len(sorted_positions) / 10))]
            if len(sorted_positions):
                self.average_profit += sum(d.get('profit', 0) for d in sorted_positions)

        
        self.printPush(f'Equity: {equity:.2f}')
        self.printPush(f'Profit: {net:.2f} USDT\tPercent: {percent:.2f}%')

        for symbol in self.closed_positions.keys():
            closed_positions = self.closed_positions[symbol]
            if len(closed_positions) == 0:
                self.printPush(f'{symbol}\tNo Positions Taken')
                continue
            total_profit = sum(float(p['profit']) for p in closed_positions)
            biggest_profit = max(float(p['profit']) for p in closed_positions)
            avg_hold_hours = (sum(p['time_elapsed'].seconds for p in closed_positions) / len(closed_positions)) / 3600.0
            avg_profit = total_profit / len(closed_positions)
            percent_of_profits = (total_profit / net) * 100.0
            self.printPush(f'{symbol: <9}\tTotal Gains: {total_profit:6.2f}\tAvg Gains: {avg_profit:5.2f}\tBiggest Gain: {biggest_profit:5.2f}\tPercent of Gains: {percent_of_profits:5.2f}%\tAvg Hold: {avg_hold_hours:0.2f}hrs')       

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
        for coin in self.markets:
            coin += 'USDT'
            self.positions[coin] = None
            self.closed_positions[coin] = []

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

            order_qty = usdtWorth/price
            order_qty = truncate(order_qty, self.precision[symbol])
            filled_qty = order_qty * (1 - 0.002)
            
            strOrder = (f'BUY\t{order_qty}\t{symbol: <9} @ {price}/ea\t{usdtWorth:.2f}')
            #buy_market = self.client.order_market_buy(symbol=symbol, quoteOrderQty=usdtWorth)
            buy_market = {
                'type': 'BUY',
                'price': price,
                'cummulativeQuoteQty': usdtWorth,
                'executedQty': filled_qty,
                'time': self.cur_time,
            }

            self.usdt -= usdtWorth
            if self.positions[symbol] == None:
                self.positions[symbol] = []
            self.positions[symbol].append(buy_market)

            self.printPush(f'{self.Timestamp()}: Equity: {self.GetEquity():.2f}\t{strOrder}')
            
            #self.refreshBalance()

        else:
            if not any(self.positions.values()):
                print(f"{symbol} | Not enough USDT to trade (minimum of $10)")

    def getSymbolBalance(self, symbol):
        if symbol in self.positions:
            return sum(float(order['executedQty']) for order in self.positions[symbol])
        return 0

    def sell(self, symbol, df):
        self.refreshBalance()

        symbol_balance = self.getSymbolBalance(symbol)

        price = df["Close"].iloc[-1]

        if symbol_balance * price > 10:

            order_qty = truncate(symbol_balance, self.precision[symbol])
            filled_qty = order_qty * (1 - 0.002)
            usdtWorth = filled_qty * price

            strOrder = (f'SELL\t{order_qty}\t{symbol: <9} @ {price}/ea\t{usdtWorth:.2f}')
            #sell_market = self.client.order_market_sell(symbol=symbol, quantity=amount)
            sell_market = {
                'type': 'BUY',
                'price': price,
                'cummulativeQuoteQty': usdtWorth,
                'executedQty': filled_qty,
                'time': self.cur_time,
            }

            usdtOpen = 0
            for position in self.positions[symbol]:
                usdtOpen += float(position['cummulativeQuoteQty'])
            usdtClose = float(sell_market['cummulativeQuoteQty'])
            usdtClose *= (1 - 0.002)
            net = usdtClose - usdtOpen
            percent = ((usdtClose / usdtOpen) - 1) * 100

            time_elapsed = sell_market['time'] - self.positions[symbol][0]['time']
            self.usdt += usdtClose
            self.positions[symbol] = None
            
            self.closed_positions[symbol].append({
                'symbol': symbol,
                'percent': percent,
                'profit': net,
                'qty': order_qty,
                'price': price,
                'volume': usdtWorth,
                'time_elapsed': time_elapsed, 
            })

            strOrder += f'\tP/L: {net:.2f} USDT {percent:.2f}%'
            self.printPush(f'{self.Timestamp()}: Equity: {self.GetEquity():.2f}\t{strOrder}')

        else:
            if not any(self.positions.values()):
                print(f"Not enough {symbol} to trade (minimum of $10)")

    def GetEquity(self):
        equity = self.usdt
        for symbol in self.positions.keys():
            if self.positions[symbol] is None:
                continue
            for position in self.positions[symbol]:
                equity += position['executedQty'] * self.cur_price[symbol]
        return equity

    def Timestamp(self):
        return self.cur_time.strftime("%Y-%m-%d %H:%M:%S")

    def generateTicks(self):
        if self.precision is None:
            self.precision = {}
        for coin in self.markets:
            coin += 'USDT'
            self.getSymbolPrecision(coin)

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

    def getKlines(self, symbol, interval, limit=500):

        if not symbol in self.klines_cache:
            self.klines_cache[symbol] = {}
        df = None
        if (not interval in self.klines_cache[symbol].keys()) or self.klines_cache[symbol][interval] is None:
            start_time = self.start_date - (self.BinanceIntervalToDelta(interval) * (limit + 1))
            end_time = self.end_date

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
                raw_klines = self.client.get_historical_klines(
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

            self.klines_cache[symbol][interval] = df

        df = self.klines_cache[symbol][interval]
        #timestamp_cur_time = Timestamp(self.cur_time.year, self.cur_time.month, self.cur_time.day, self.cur_time.hour, self.cur_time.minute)

        time_delta = self.BinanceIntervalToDelta(interval)
        end_date = pd.Timestamp(self.cur_time)
        start_date = pd.Timestamp(self.cur_time - (time_delta * limit))
        if len(df) == 0 or df.iloc[0]['Open Time'] > start_date:
            return []
        mask = (df.index >= start_date - time_delta) & (df.index <= end_date)
        range = df.loc[mask]

        if len(range) == 0:
            return range
        if len(range) < limit - 5:
            self.klines_cache[symbol][interval] = None
            return self.getKlines(symbol, interval, limit)

        return range

    def BinanceIntervalToDelta(self, interval):
        if interval == Client.KLINE_INTERVAL_15MINUTE:
            return timedelta(minutes=15)
        elif interval == Client.KLINE_INTERVAL_4HOUR:
            return timedelta(hours=4)

    def refreshBalance(self):
        return

    def printPush(self, text):
        print(text)
        self.queuePush(text)

    def queuePush(self, text):
        self.queuedMessages.append(text)

    def PushQueuedAsOne(self):
        self.Push("\r\n".join(self.queuedMessages))
        self.queuedMessages.clear()

    def PushQueued(self):
        while self.queuedMessages:
            self.Push(self.queuedMessages.pop(0))
        
    def Push(self, text):
        return