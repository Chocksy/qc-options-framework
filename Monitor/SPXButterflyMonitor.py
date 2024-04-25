#region imports
from AlgorithmImports import *
#endregion

from .Base import Base
from CustomIndicators import ATRLevels
from Tools import Underlying
from Strategy import WorkingOrder

class SPXButterflyMonitor(Base):
    DEFAULT_PARAMETERS = {
        # The frequency (in minutes) with which each position is managed
        "managePositionFrequency": 5,
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        "profitTarget": 0.3,
        # Stop Loss Multiplier, expressed as a function of the profit target (rather than the credit received)
        # The position is closed (Market Order) if:
        #    Position P&L < -abs(openPremium) * stopLossMultiplier
        # where:
        #  - openPremium is the premium received (positive) in case of credit strategies
        #  - openPremium is the premium paid (negative) in case of debit strategies
        #
        # Credit Strategies (i.e. $2 credit):
        #  - profitTarget < 1 (i.e. 0.5 -> 50% profit target -> $1 profit)
        #  - stopLossMultiplier = 2 * profitTarget (i.e. -abs(openPremium) * stopLossMultiplier = -abs(2) * 2 * 0.5 = -2 --> stop if P&L < -2$)
        # Debit Strategies (i.e. $4 debit):
        #  - profitTarget < 1 (i.e. 0.5 -> 50% profit target -> $2 profit)
        #  - stopLossMultiplier < 1 (You can't lose more than the debit paid. i.e. stopLossMultiplier = 0.6 --> stop if P&L < -2.4$)
        # self.stopLossMultiplier = 3 * self.profitTarget
        # self.stopLossMultiplier = 0.6
        "stopLossMultiplier": 0.7,
        # Ensures that the Stop Loss does not exceed the theoretical loss. (Set to False for Credit Calendars)
        "capStopLoss": True,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context)
        self.fiveMinuteITM = {}
        self.HODLOD = {}
        self.triggerHODLOD = {}
        # The dictionary of consolidators
        self.consolidators = dict()
        # self.ATRLevels = ATRLevels("ATRLevels", length = 14)
        # EMAs for the 8, 21 and 34 periods
        self.EMAs = {8: {}, 21: {}, 34: {}}
        # self.stdDevs = {}
        # Add a dictionary to keep track of whether the position reached 50% profit
        self.reachedHalfProfit = {}

    def monitorPosition(self, position):
        pass

    def shouldClose(self, position):
        return False, None

    