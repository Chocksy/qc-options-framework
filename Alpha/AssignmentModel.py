#region imports
from AlgorithmImports import *
#endregion

from .Base import Base

class AssignmentModel(Base):
    PARAMETERS = {
        # The start time at which the algorithm will start scheduling the strategy execution (to open new positions). No positions will be opened before this time
        "scheduleStartTime": time(9, 30, 0),
        # The stop time at which the algorithm will look to open a new position.
        "scheduleStopTime": time(16, 0, 0),
        # Periodic interval with which the algorithm will check to open new positions
        "scheduleFrequency": timedelta(minutes = 5),
        # Maximum number of open positions at any given time
        "maxActivePositions": 1,
        # Control whether to allow multiple positions to be opened for the same Expiration date
        "allowMultipleEntriesPerExpiry": False,
        # Minimum time distance between opening two consecutive trades
        "minimumTradeScheduleDistance": timedelta(minutes=10),
        # Days to Expiration
        "dte": 7,
        # The size of the window used to filter the option chain: options expiring in the range [dte-dteWindow, dte] will be selected
        "dteWindow": 14,
        "useLimitOrders": True,
        "limitOrderRelativePriceAdjustment": 0.2,
        # Alternative method to set the absolute price (per contract) of the Limit Order. This method is used if a number is specified
        "limitOrderAbsolutePrice": 1.0,
        "limitOrderExpiration": timedelta(minutes=15),
        # Coarse filter for the Universe selection. It selects nStrikes on both sides of the ATM
        # strike for each available expiration
        # Example: 200 SPX @ 3820 & 3910C w delta @ 1.95 => 90/5 = 18
        "nStrikesLeft": 35,
        "nStrikesRight": 35,
        # TODO fix this and set it based on buying power.
        # "maxOrderQuantity": 25,
        "validateQuantity": False,
        "targetPremiumPct": 0.015,
        # Minimum premium accepted for opening a new position. Setting this to None disables it.
        "minPremium": 0.8,
        # Maximum premium accepted for opening a new position. Setting this to None disables it.
        "maxPremium": 2.0,
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        "profitTarget": 1.0,
        # "bidAskSpreadRatio": 0.4,
        "validateBidAskSpread": False,
        "marketCloseCutoffTime": None, #time(15, 45, 0),
        # Put/Call Wing size for Iron Condor, Iron Fly
        # "targetPremium": 500,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context)
        # You can change the name here
        self.name = "AssignmentModel"
        self.nameTag = "AssignmentModel"
        self.ticker = "TSLA"
        self.context.structure.AddUnderlying(self, self.ticker)

    @classmethod
    def handleAssignment(cls, context, assignedPosition):
        context.logger.info(f"AssignmentModel handleAssignment called for {assignedPosition}")

    def getOrder(self, chain, data):
        if data.ContainsKey(self.underlyingSymbol):
            self.logger.debug(f"AssignmentModel -> getOrder: Data contains key {self.underlyingSymbol}")
            # Based on maxActivePositions set to 1. We should already check if there is an open position or
            # working order. If there is, then this will not even run.
            call =  self.order.getSpreadOrder(
                chain,
                'call',
                fromPrice=self.minPremium,
                toPrice=self.maxPremium,
                wingSize=5,
                sell=True
            )
            self.logger.debug(f"AssignmentModel -> getOrder: Call: {call}")
            if call is not None:
                return [call]
            else:
                return None
        else:
            return None


