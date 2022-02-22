import talib
from collections import namedtuple
from Util import *


def strategyDecision(fma, sma):
    # fma = fma
    # sma = sma

    return strategyCalculator(fma, sma)


def strategyCalculator(fma, sma):

    enterLongCondition = Crossover(fma, sma)
    exitLongCondition =  Crossover(sma, fma)
    #exitLongCondition = fma.iloc[-1] < sma.iloc[-1] 
    
    # # MOMENTUM
    # longEmaCondition = ema8 > ema13 and ema13 > ema21 and ema21 > ema34 and ema34 > ema55
    # exitLongEmaCondition = ema21 < ema55

    # # RSI
    # longRsiCondition = rsi < 65
    # exitLongRsiCondition = rsi > 70

    # # STOCHASTIC
    # longStochasticCondition = kFast < 80
    # exitLongStochasticCondition = kFast > 95

    # # STRAT
    # enterLongCondition = longEmaCondition and longRsiCondition and longStochasticCondition
    # exitLongCondition = (
    #     exitLongEmaCondition or exitLongRsiCondition or exitLongStochasticCondition)

    return (enterLongCondition, exitLongCondition)


def calculateIndicators(klines, klines4h):

    ha_t = klines
    ha_t4 = klines4h
    # ha_t = HA(klines)
    # ha_t4 = HA(klines4h)
    
    # ha_t4 = ha_t4.set_index(['Open Time'])
    # ha_t4 = ha_t4.resample('15min').ffill()
    # end_date = klines['Open Time'].iloc[-1]
    # idx = pd.date_range(ha_t4.index.min(), end_date, freq="15min")
    # ha_t4 = ha_t4.reindex(idx, method='ffill')

    fma = ha_t4['HA_Close'] #talib.EMA(ha_t4['HA_Close'], timeperiod=1)
    sma = talib.EMA(ha_t['HA_Close'], timeperiod=5)

    # fma = fma[:-1]#delete last element
    # sma = sma[:-1]

    return strategyDecision(fma, sma)
    
