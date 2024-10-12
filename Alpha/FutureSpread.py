#region imports
from AlgorithmImports import *
#endregion

from .Base import Base

class FutureSpread(Base):
    PARAMETERS = {
        # The start time at which the algorithm will start scheduling the strategy execution (to open new positions). No positions will be opened before this time
        "scheduleStartTime": time(9, 30, 0),
        # The stop time at which the algorithm will look to open a new position.
        "scheduleStopTime": time(16, 0, 0),
        # Periodic interval with which the algorithm will check to open new positions
        "scheduleFrequency": timedelta(minutes = 5),
        # Maximum number of open positions at any given time
        "maxActivePositions": 10,
        # Maximum number of open orders (not filled) at any given time
        "maxOpenPositions":1,
        # Control whether to allow multiple positions to be opened for the same Expiration date
        "allowMultipleEntriesPerExpiry": True,
        # Minimum time distance between opening two consecutive trades
        "minimumTradeScheduleDistance": timedelta(minutes=10),
        # Days to Expiration
        "dte": 150,  # Adjust this based on the futures contract you want to trade
        # The size of the window used to filter the option chain: options expiring in the range [dte-dteWindow, dte] will be selected
        "dteWindow": 150,
        "useLimitOrders": True,
        "limitOrderRelativePriceAdjustment": 0.2,
        # Alternative method to set the absolute price (per contract) of the Limit Order. This method is used if a number is specified
        "limitOrderAbsolutePrice": 1.0,
        "limitOrderExpiration": timedelta(minutes=5),
        # Coarse filter for the Universe selection. It selects nStrikes on both sides of the ATM
        # strike for each available expiration
        # Example: 200 SPX @ 3820 & 3910C w delta @ 1.95 => 90/5 = 18
        "nStrikesLeft": 5,
        "nStrikesRight": 5,
        # TODO fix this and set it based on buying power.
        # "maxOrderQuantity": 200,
        # COMMENT OUT this one below because it caused the orderQuantity to be 162 and maxOrderQuantity to be 10 so it would not place trades.
        "targetPremiumPct": 0.01,
        "validateQuantity": False,
        # Minimum premium accepted for opening a new position. Setting this to None disables it.
        "minPremium": 0.5,
        # Maximum premium accepted for opening a new position. Setting this to None disables it.
        "maxPremium": 2.0,
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        "profitTarget": 1.0,
        "bidAskSpreadRatio": 0.4,
        "validateBidAskSpread": True,
        "marketCloseCutoffTime": time(15, 45, 0),
        # Put/Call Wing size for Iron Condor, Iron Fly
        "putWingSize": 5,
        "callWingSize": 5,
        # "targetPremium": 500,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context)
        # You can change the name here
        self.name = "FutureSpread"
        self.nameTag = "FutureSpread"
        self.ticker = Futures.Indices.SP_500_E_MINI # "ES1!"
        self.context.structure.AddUnderlying(self, self.ticker)
        self.logger.debug(f"{self.__class__.__name__} -> __init__ -> AddUnderlying")


    def getOrder(self, chain, data):
        self.logger.debug(f"{self.__class__.__name__} -> getOrder -> start")
        self.logger.debug(f"FutureSpread -> getOrder -> data.ContainsKey(self.underlyingSymbol): {data.ContainsKey(self.underlyingSymbol)}")
        self.logger.debug(f"FutureSpread -> getOrder -> Underlying Symbol: {self.underlyingSymbol}")
        # Best time to open the trade: 9:45 + 10:15 + 12:30 + 13:00 + 13:30 + 13:45 + 14:00 + 15:00 + 15:15 + 15:45
        # https://tradeautomationtoolbox.com/byob-ticks/?save=admZ4dG
        if data.ContainsKey(self.underlyingSymbol):
            self.logger.debug(f"FutureSpread -> getOrder: Data contains key {self.underlyingSymbol}")
            # trade_times = [time(9, 45, 0), time(10, 15, 0), time(12, 30, 0), time(13, 0, 0), time(13, 30, 0), time(13, 45, 0), time(14, 0, 0)]
            trade_times = [time(9, 45, 0), time(10, 15, 0), time(12, 30, 0), time(13, 0, 0), time(13, 30, 0), time(13, 45, 0), time(14, 0, 0)]
            # trade_times = [time(hour, minute, 0) for hour in range(9, 15) for minute in range(0, 60, 30) if not (hour == 15 and minute > 0)]
            # Remove the microsecond from the current time
            current_time = self.context.Time.time().replace(microsecond=0)
            self.logger.debug(f"FutureSpread -> getOrder -> current_time: {current_time}")
            self.logger.debug(f"FutureSpread -> getOrder -> trade_times: {trade_times}")
            self.logger.debug(f"FutureSpread -> getOrder -> current_time in trade_times: {current_time in trade_times}")
            if current_time not in trade_times:
                return None

            put = self.order.getSpreadOrder(
                chain,
                'put',
                fromPrice=self.minPremium,
                toPrice=self.maxPremium,
                wingSize=self.putWingSize,
                sell=True
            )
            self.logger.debug(f"SPXic -> getOrder: Put: {put}")
            if put is not None:
                return [put]
            else:
                return None
        else:
            return None

