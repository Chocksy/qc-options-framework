#region imports
from AlgorithmImports import *
from collections import deque
from scipy import stats
from numpy import mean, array
#endregion

# Indicator from https://www.satyland.com/atrlevels by Saty

# Use like this:
# 
# self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol        
# self.ATRLevels = ATRLevels("ATRLevels", length = 14)
# algorithm.RegisterIndicator(self.ticker, self.ATRLevels, Resolution.Daily)
# self.algorithm.WarmUpIndicator(self.ticker, self.ATRLevels, Resolution.Daily)


# // Set the appropriate timeframe based on trading mode
# timeframe_func() => 
#     timeframe = "D"
#     if trading_type == day_trading
#         timeframe := "D"
#     else if trading_type == multiday_trading
#         timeframe := "W"
#     else if trading_type == swing_trading
#         timeframe := "M"
#     else if trading_type == position_trading
#         timeframe := "3M"
#     else
#         timeframe := "D"

class ATRLevels(PythonIndicator):
    TriggerPercentage = 0.236
    MiddlePercentage = 0.618
    
    def __init__(self, name, length = 14):
        # default indicator definition
        super().__init__()
        self.Name = name
        self.Value = 0
        self.Time = datetime.min

        # set automatic warmup period + 1 day
        self.WarmUpPeriod = length + 1

        self.length = length
    
        self.ATR = AverageTrueRange(self.length)

        # Holds 2 values the current close and the previous day/period close.
        self.PreviousCloseQueue = deque(maxlen=2)

        # Indicator to hold the period close, high, low, open
        self.PeriodHigh = Identity('PeriodHigh')
        self.PeriodLow = Identity('PeriodLow')
        self.PeriodOpen = Identity('PeriodOpen')

    @property
    def IsReady(self) -> bool:
        return self.ATR.IsReady

    def Update(self, input) -> bool:
        # update all the indicators with the new data
        dataPoint = IndicatorDataPoint(input.Symbol, input.EndTime, input.Close)
        bar = TradeBar(input.Time, input.Symbol, input.Open, input.High, input.Low, input.Close, input.Volume)     
        ## Update SMA with data time and volume
        # symbolSMAv.Update(tuple.Index, tuple.volume)
        # symbolRSI.Update(tuple.Index, tuple.close)
        # symbolADX.Update(bar)
        # symbolATR.Update(bar)
        # symbolSMA.Update(tuple.Index, tuple.close)
        self.ATR.Update(bar)
        self.PreviousCloseQueue.appendleft(dataPoint)
        self.PeriodHigh.Update(input.Time, input.High)
        self.PeriodLow.Update(input.Time, input.Low)
        self.PeriodOpen.Update(input.Time, input.Open)
        
        if self.ATR.IsReady and len(self.PreviousCloseQueue) == 2:
            self.Time = input.Time
            self.Value = self.PreviousClose().Value

        return self.IsReady

    # Returns the previous close value of the period. 
    # @return [Float]
    def PreviousClose(self):
        if len(self.PreviousCloseQueue) == 1: return None
        return self.PreviousCloseQueue[0]

    # Bear level method. This is represented usually as a yellow line right under the close line.
    # @return [Float]
    def LowerTrigger(self):
        return self.PreviousClose().Value - (self.TriggerPercentage * self.ATR.Current.Value) # biggest value 1ATR
    
    # Lower Midrange level. This is under the lowerTrigger (yellow line) and above the -1ATR line(lowerATR)
    # @return [Float]
    def LowerMiddle(self):
        return self.PreviousClose().Value - (self.MiddlePercentage * self.ATR.Current.Value)

    # Lower -1ATR level.
    # @return [Float]
    def LowerATR(self):
        return self.PreviousClose().Value - self.ATR.Current.Value

    # Lower Extension level.
    # @return [Float]
    def LowerExtension(self):
        return self.LowerATR() - (self.TriggerPercentage * self.ATR.Current.Value)

    # Lower Midrange Extension level.
    # @return [Float]
    def LowerMiddleExtension(self):
        return self.LowerATR() - (self.MiddlePercentage * self.ATR.Current.Value)

    # Lower -2ATR level.
    # @return [Float]
    def Lower2ATR(self):
        return self.LowerATR() - self.ATR.Current.Value

    # Lower -2ATR Extension level.
    # @return [Float]
    def Lower2ATRExtension(self):
        return self.Lower2ATR() - (self.TriggerPercentage * self.ATR.Current.Value)
    
    # Lower -2ATR Midrange Extension level.
    # @return [Float]
    def Lower2ATRMiddleExtension(self):
        return self.Lower2ATR() - (self.MiddlePercentage * self.ATR.Current.Value)

    # Lower -3ATR level.
    # @return [Float]
    def Lower3ATR(self):
        return self.Lower2ATR() - self.ATR.Current.Value

    def BearLevels(self):
        return [
            self.LowerTrigger(), 
            self.LowerMiddle(), 
            self.LowerATR(), 
            self.LowerExtension(), 
            self.LowerMiddleExtension(), 
            self.Lower2ATR(), 
            self.Lower2ATRExtension(), 
            self.Lower2ATRMiddleExtension(),
            self.Lower3ATR()
        ]

    # Bull level method. This is represented usually as a blue line right over the close line.
    # @return [Float]
    def UpperTrigger(self):
        return self.PreviousClose().Value + (self.TriggerPercentage * self.ATR.Current.Value)  # biggest value 1ATR
    
    # Upper Midrange level.
    # @return [Float]
    def UpperMiddle(self):
        return self.PreviousClose().Value + (self.MiddlePercentage * self.ATR.Current.Value)
    
    # Upper 1ATR level.
    # @return [Float]
    def UpperATR(self):
        return self.PreviousClose().Value + self.ATR.Current.Value

    # Upper Extension level.
    # @return [Float]
    def UpperExtension(self):
        return self.UpperATR() + (self.TriggerPercentage * self.ATR.Current.Value)

    # Upper Midrange Extension level.
    # @return [Float]
    def UpperMiddleExtension(self):
        return self.UpperATR() + (self.MiddlePercentage * self.ATR.Current.Value)

    # Upper 2ATR level.
    def Upper2ATR(self):
        return self.UpperATR() + self.ATR.Current.Value
    
    # Upper 2ATR Extension level.
    # @return [Float]
    def Upper2ATRExtension(self):
        return self.Upper2ATR() + (self.TriggerPercentage * self.ATR.Current.Value)
    
    # Upper 2ATR Midrange Extension level.
    # @return [Float]
    def Upper2ATRMiddleExtension(self):
        return self.Upper2ATR() + (self.MiddlePercentage * self.ATR.Current.Value)

    # Upper 3ATR level.
    # @return [Float]
    def Upper3ATR(self):
        return self.Upper2ATR() + self.ATR.Current.Value

    def BullLevels(self):
        return [
            self.UpperTrigger(), 
            self.UpperMiddle(), 
            self.UpperATR(), 
            self.UpperExtension(), 
            self.UpperMiddleExtension(), 
            self.Upper2ATR(), 
            self.Upper2ATRExtension(), 
            self.Upper2ATRMiddleExtension(),
            self.Upper3ATR()
        ]

    def NextLevel(self, LevelNumber, bull = False, bear = False):
        dayOpen = self.PreviousClose().Value
        allLevels = [dayOpen] + self.BearLevels() + self.BullLevels()
        allLevels = sorted(allLevels, key = lambda x: x, reverse = False)
        bearLs = sorted(filter(lambda x: x <= dayOpen, allLevels), reverse = True)
        bullLs = list(filter(lambda x: x >= dayOpen, allLevels))

        if bull:
            return bullLs[LevelNumber]
        if bear:
            return bearLs[LevelNumber]
        return None

    def Range(self):
        return self.PeriodHigh.Current.Value - self.PeriodLow.Current.Value

    def PercentOfAtr(self):
        return (self.Range() / self.ATR.Current.Value) * 100

    def Warmup(self, history):
        for index, row in history.iterrows():
            self.Update(row)

    # Method to return a string with the bull and bear levels.
    # @return [String]
    def ToString(self):
        return "Bull Levels: [{}]; Bear Levels: [{}]".format(self.BullLevels(), self.BearLevels())
