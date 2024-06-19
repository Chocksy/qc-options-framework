#region imports
from AlgorithmImports import *
#endregion

from .Base import Base

class SPXButterfly(Base):
    PARAMETERS = {
        # The start time at which the algorithm will start scheduling the strategy execution (to open new positions). No positions will be opened before this time
        "scheduleStartTime": time(9, 30, 0),
        # The stop time at which the algorithm will look to open a new position.
        "scheduleStopTime": time(16, 0, 0),
        # Periodic interval with which the algorithm will check to open new positions
        "scheduleFrequency": timedelta(minutes = 15),
        # Maximum number of open positions at any given time
        "maxActivePositions": 30,
        # Control whether to allow multiple positions to be opened for the same Expiration date
        "allowMultipleEntriesPerExpiry": True,
        # Minimum time distance between opening two consecutive trades
        "minimumTradeScheduleDistance": timedelta(minutes=10),
        # Days to Expiration
        "dte": 0,
        # The size of the window used to filter the option chain: options expiring in the range [dte-dteWindow, dte] will be selected
        "dteWindow": 0,
        "useLimitOrders": True,
        "limitOrderRelativePriceAdjustment": 0.2,
        # Alternative method to set the absolute price (per contract) of the Limit Order. This method is used if a number is specified
        "limitOrderExpiration": timedelta(minutes=20),
        # Coarse filter for the Universe selection. It selects nStrikes on both sides of the ATM
        # strike for each available expiration
        # Example: 200 SPX @ 3820 & 3910C w delta @ 1.95 => 90/5 = 18
        "nStrikesLeft": 18,
        "nStrikesRight": 18,
        # TODO fix this and set it based on buying power.
        "maxOrderQuantity": 1000,
        "targetPremiumPct": 0.015,
        # Minimum premium accepted for opening a new position. Setting this to None disables it.
        "minPremium": None,
        # Maximum premium accepted for opening a new position. Setting this to None disables it.
        "maxPremium": None,
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        # "profitTarget": 1.0,
        "bidAskSpreadRatio": 0.4,
        "validateBidAskSpread": True,
        "marketCloseCutoffTime": time(16, 10, 0),
        # Put/Call Wing size for Iron Condor, Iron Fly
        "butterflyLeftWingSize": 35,
        "butterflyRightWingSize": 35,
        # "targetPremium": 500,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context)
        # You can change the name here
        self.name = "SPXButterfly"
        self.nameTag = "SPXButterfly"
        self.ticker = "SPX"
        self.context.structure.AddUnderlying(self, self.ticker)

    def getOrder(self, chain, data):
        # Open trades at 13:00
        if data.ContainsKey(self.underlyingSymbol):
            trade_times = [time(9, 45, 0)]
            current_time = self.context.Time.time()
            if current_time not in trade_times:
                return None
            fly =  self.order.getIronFlyOrder(
                chain,
                callWingSize=self.butterflyLeftWingSize,
                putWingSize=self.butterflyRightWingSize,
                sell=True
            )
            if fly is not None:
                return fly
            else:
                return None
        else:
            return None

        


