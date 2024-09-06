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
        "profitTarget": 1,
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
        "stopLossMultiplier": 1.9,
        # Ensures that the Stop Loss does not exceed the theoretical loss. (Set to False for Credit Calendars)
        "capStopLoss": True,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context, 'SPXButterfly')
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
        """
        TODO:
        - check if ATR indicator has been breached and exit
        - check if half premium was reached and close 50%-80% of position (not really possible now as we have a True/False return)
        """
        score = 0
        reason = ""
        stats = position.strategy.stats

        # Assign a score of 3 if 5m ITM threshold is met
        # if position.orderTag in self.fiveMinuteITM and self.fiveMinuteITM[position.orderTag]:
        #     score += 3
            # reason = "5m ITM"

        # Assign a score of 1 if HOD/LOD breach occurs
        # if position.orderTag in self.HODLOD and self.HODLOD[position.orderTag] and position.underlyingSymbol() in stats.touchedEMAs and stats.touchedEMAs[position.underlyingSymbol()]:
        #     score += 1
        #     reason = "HOD/LOD"

        # Assign a score of 2 if the position reached 50% profit and is now at break-even or slight loss
        # if position.orderTag in self.reachedHalfProfit and self.reachedHalfProfit[position.orderTag] and position.positionPnL <= 0:
        #     score += 2
        #     reason = "Reached 50% profit"

        # Return True if the total score is 3 or more
        # if score >= 3:
        #     return True, reason

        return False, ""

    