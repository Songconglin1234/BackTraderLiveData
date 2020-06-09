import backtrader as bt
import backtrader.indicators as btind
import datetime
import pandas as pd
from pandas import Series, DataFrame
import random
from copy import deepcopy
# Loaded backend TkAgg version unknown? ANd  finding fonts debug msgs... https://github.com/matplotlib/matplotlib/issues/14523
import logging
logging.getLogger('matplotlib.font_manager').disabled = True
 
class SMAC(bt.Strategy):
    """A simple moving average crossover strategy; crossing of a fast and slow moving average generates buy/sell
       signals"""
    params = {"fast": 20, "slow": 50,                  # The windows for both fast and slow moving averages
              "optim": False, "optim_fs": (20, 50)}    # Used for optimization; equivalent of fast and slow, but a tuple
                                                       # The first number in the tuple is the fast MA's window, the
                                                       # second the slow MA's window
    def __init__(self):
        """Initialize the strategy"""
        print ("Inititalizing the strategy")
        self.fastma = dict()
        self.slowma = dict()
        self.regime = dict()
        self.delta1 = dict()
        self.delta2 = dict()
        self.delta3 = dict()
        self.hma4 = dict()
        self.hma9 = dict()
        self.hma16 = dict()
        self.hma25 = dict()
 
        self._addobserver(True, bt.observers.BuySell)    # CAUTION: Abuse of the method, I will change this in future code (see: https://community.backtrader.com/topic/473/plotting-just-the-account-s-value/4)
 
        if self.params.optim:    # Use a tuple during optimization
            self.params.fast, self.params.slow = self.params.optim_fs    # fast and slow replaced by tuple's contents
 
        if self.params.fast > self.params.slow:
            raise ValueError(
                "A SMAC strategy cannot have the fast moving average's window be " + \
                 "greater than the slow moving average window.")
        print ("Here are my data names: {0}".format (self.getdatanames()))
        for d in self.getdatanames():
 
            # The moving averages
            self.fastma[d] = btind.SimpleMovingAverage(self.getdatabyname(d),      # The symbol for the moving average
                                                       period=self.params.fast,    # Fast moving average
                                                       plotname="FastMA: " + d)
            self.slowma[d] = btind.SimpleMovingAverage(self.getdatabyname(d),      # The symbol for the moving average
                                                      period=self.params.slow,    # Slow moving average
                                                       plotname="SlowMA: " + d)
 
            self.hma25[d] = btind.HullMovingAverage(self.getdatabyname(d),            # The symbol for the moving average
                                                       period=25,    # Hull moving average
                                                       plotname="HullMA: " + d)
            # Get the regime
            self.regime[d] = self.fastma[d] - self.slowma[d]    # Positive when bullish
 
            print ("Strategy initialization finished.")
 
    def next(self):
        """Define what will be done in a single step, including creating and closing trades"""
        
        print ("Running strategy.next on: {0}".format(self.getdatanames()))
        for d in self.getdatanames():    # Looping through all symbols
            print ("datetime: {0}".format (self.data.datetime.time()))
            if self.data.datetime.time() == datetime.time(9,30):
                print ("Open of new day")
            accel2_bool = (self.hma25[d][-2] + self.hma25[d][0])/2 > self.hma25[d][-1]
            pos = self.getpositionbyname(d).size or 0
            if pos == 0:    # Are we out of the market?
                # Consider the possibility of entrance
                # Notice the indexing; [0] always mens the present bar, and [-1] the bar immediately preceding
                # Thus, the condition below translates to: "If today the regime is bullish (greater than
                # 0) and yesterday the regime was not bullish"
                if (self.hma25[d] > self.fastma[d] 
                    and accel2_bool):  # A buy signal
                    self.buy(data=self.getdatabyname(d))
 
            else:    # We have an open position
                if self.regime[d] < 0 or not accel2_bool: # A sell signal
                    self.sell(data=self.getdatabyname(d))
 
class PropSizer(bt.Sizer):
    """A position sizer that will buy as many stocks as necessary for a certain proportion of the portfolio
       to be committed to the position, while allowing stocks to be bought in batches (say, 100)"""
    params = {"prop": 0.1, "batch": 100}
 
    def _getsizing(self, comminfo, cash, data, isbuy):
        """Returns the proper sizing"""
 
        if isbuy:    # Buying
            target = self.broker.getvalue() * self.params.prop    # Ideal total value of the position
            price = data.close[0]
            shares_ideal = target / price    # How many shares are needed to get target
            batches = int(shares_ideal / self.params.batch)    # How many batches is this trade?
            shares = batches * self.params.batch    # The actual number of shares bought
 
            if shares * price > cash:
                return 0    # Not enough money for this trade
            else:
                return shares
 
        else:    # Selling
            return self.broker.getposition(data).size    # Clear the position
 
cerebro = bt.Cerebro(stdstats=False)    # I don't want the default plot objects
cerebro.broker.set_cash(1000000)    # Set our starting cash to $1,000,000
cerebro.broker.setcommission(0.02)
 
start = datetime.datetime(2020, 3, 1)
end = datetime.datetime(2020, 6, 8)
 
# create the data
usestore = True     
 
storekwargs = dict(
        host= '127.0.0.1', port=7497,
        clientId=None, timeoffset=False,
        reconnect=3, timeout=3.0,
        notifyall=False, _debug=False
)
ibstore = bt.stores.IBStore(**storekwargs)
print ("Using IBstore")
 
broker = ibstore.getbroker()
IBDataFactory = ibstore.getdata if usestore else bt.feeds.IBData
dtfmt = '%Y-%m-%dT%H:%M:%S.%f'
datakwargs = dict(
        timeframe= bt.TimeFrame.TFrame("Minutes"), compression=5,
        historical=True, fromdate=start, todate = end,     ## mod todate here
        rtbar=False,
        qcheck=0.5,
        what=None,
        backfill_start=True,
        backfill=False,
        latethrough=False,
        tz=None,
        useRTH = True
)
    
data0 = IBDataFactory(dataname='PDD', **datakwargs)
data0.plotinfo.plotmaster = data0
 
cerebro.adddata(data0)    # Give the data to cerebro
 
print("Data added to cerebro")
class AcctValue(bt.Observer):
    alias = ('Value',)
    lines = ('value',)
 
    plotinfo = {"plot": True, "subplot": True}
 
    def next(self):
        self.lines.value[0] = self._owner.broker.getvalue()    # Get today's account value (cash + stocks)
 
cerebro.addobserver(AcctValue)
cerebro.addstrategy(SMAC)
cerebro.addsizer(PropSizer)
 
cerebro.broker.getvalue()
 
cerebro.run()
cerebro.plot()