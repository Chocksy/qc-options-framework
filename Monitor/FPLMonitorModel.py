#region imports
from AlgorithmImports import *
#endregion

from .Base import Base
from CustomIndicators import ATRLevels
from Tools import Underlying
from Strategy import WorkingOrder

class FPLMonitorModel(Base):
    DEFAULT_PARAMETERS = {
        # The frequency (in minutes) with which each position is managed
        "managePositionFrequency": 1,
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        "profitTarget": 0.5,
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
        "stopLossMultiplier": 2,
        # Ensures that the Stop Loss does not exceed the theoretical loss. (Set to False for Credit Calendars)
        "capStopLoss": True,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context, 'FPLModel')
        self.fiveMinuteITM = {}
        self.HODLOD = {}
        self.triggerHODLOD = {}
        # The dictionary of consolidators
        self.consolidators = dict()
        self.ATRLevels = ATRLevels("ATRLevels", length = 14)
        # EMAs for the 8, 21 and 34 periods
        self.EMAs = {8: {}, 21: {}, 34: {}}
        # self.stdDevs = {}
        # Add a dictionary to keep track of whether the position reached 50% profit
        self.reachedHalfProfit = {}

    def monitorPosition(self, position):
        """
        TODO:
        # These can be complementar
        - check if 2x(1.0) premium was reached and increase position quantity
        - check if 2.5x(1.5) premium was reached and increase position
        """
        symbol = position.underlyingSymbol()
        underlying = Underlying(self.context, position.underlyingSymbol())
        
        # Check if any price in the priceProgressList reached 50% profit
        if any(abs(price*100) / abs(position.openOrder.fillPrice*100) <= 0.5 for price in position.priceProgressList):
            self.reachedHalfProfit[position.orderTag] = True

        # Check if the price of the position reaches 1.0 premium (adding a buffer so we can try and get a fill at 1.0)
        if any(price / abs(position.openOrder.fillPrice) >= 0.9 for price in position.priceProgressList):
            # Increase the quantity by 50%
            new_quantity = position.Quantity * 1.5
            orderTag = position.orderTag
            orderId = position.orderId
            self.context.workingOrders[orderTag] = WorkingOrder(
                orderId=orderId,
                useLimitOrder=True,
                orderType="update",
                limitOrderPrice=1.0,
                fills=0,
                quantity=new_quantity
            )

        bar = underlying.Security().GetLastData()
        stats = position.strategy.stats

        if bar is not None:
            high = bar.High
            low = bar.Low

            for period, emas in self.EMAs.items():
                if symbol in emas:
                    ema = emas[symbol]
                    if ema.IsReady:
                        if low <= ema.Current.Value <= high:
                            # The price has touched the EMA
                            stats.touchedEMAs[symbol] = True

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
        if position.orderTag in self.fiveMinuteITM and self.fiveMinuteITM[position.orderTag]:
            score += 3
            reason = "5m ITM"

        # Assign a score of 1 if HOD/LOD breach occurs
        if position.orderTag in self.HODLOD and self.HODLOD[position.orderTag] and position.underlyingSymbol() in stats.touchedEMAs and stats.touchedEMAs[position.underlyingSymbol()]:
            score += 1
            reason = "HOD/LOD"

        # Assign a score of 2 if the position reached 50% profit and is now at break-even or slight loss
        if position.orderTag in self.reachedHalfProfit and self.reachedHalfProfit[position.orderTag] and position.positionPnL <= 0:
            score += 2
            reason = "Reached 50% profit"

        # Return True if the total score is 3 or more
        if score >= 3:
            return True, reason

        return False, ""

    def preManageRisk(self):
        # Check if it's time to plot and return if it's not the 1 hour mark
        if self.context.Time.minute % 60 != 0:
            return
        
        # Plot ATR Levels on the "Underlying Price" chart
        for i, level in enumerate(self.ATRLevels.BullLevels()[:3]):
            self.context.Plot("Underlying Price", f"Bull Level {i+1}", level)
        for i, level in enumerate(self.ATRLevels.BearLevels()[:3]):
            self.context.Plot("Underlying Price", f"Bear Level {i+1}", level)

        
        # Loop through all open positions
        for _orderTag, orderId in list(self.context.openPositions.items()):
            # Get the book position
            bookPosition = self.context.allPositions[orderId]

            # TODO: 
            #   if price is 1.0x premium received, increase position quantity
            #   if price is 1.5x premium received, increase position quantity



        return super().preManageRisk()

    def on5MinuteData(self, sender: object, consolidated_bar: TradeBar) -> None:
        """
        On a new 5m bar we check if we should close the position.
        """
        # pass
        for _orderTag, orderId in list(self.context.openPositions.items()):
            # Get the book position
            bookPosition = self.context.allPositions[orderId]

        #     if bookPosition.strategyId == "IronCondor":
        #         continue

        #     self.handleHODLOD(bookPosition, consolidated_bar)

            self.handleFiveMinuteITM(bookPosition, consolidated_bar)

    def on15MinuteData(self, sender: object, consolidated_bar: TradeBar) -> None:
        for _orderTag, orderId in list(self.context.openPositions.items()):
            # Get the book position
            bookPosition = self.context.allPositions[orderId]

            if bookPosition.strategyId == "IronCondor":
                continue

            self.handleHODLOD(bookPosition, consolidated_bar)
        # pass

    def OnSecuritiesChanged(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        super().OnSecuritiesChanged(algorithm, changes)
        for security in changes.AddedSecurities:
            if security.Type != SecurityType.Equity and security.Type != SecurityType.Index:
                continue
            self.context.logger.info(f"Adding consolidator for {security.Symbol}")
            
            self.consolidators[security.Symbol] = []
            # Creating a 5-minute consolidator.
            consolidator5m = TradeBarConsolidator(timedelta(minutes=5))
            consolidator5m.DataConsolidated += self.on5MinuteData
            self.context.SubscriptionManager.AddConsolidator(security.Symbol, consolidator5m)
            self.consolidators[security.Symbol].append(consolidator5m)
            # Creating a 15-minute consolidator.
            consolidator15m = TradeBarConsolidator(timedelta(minutes=15))
            consolidator15m.DataConsolidated += self.on15MinuteData
            self.context.SubscriptionManager.AddConsolidator(security.Symbol, consolidator15m)
            self.consolidators[security.Symbol].append(consolidator15m)
            # Creating the Daily ATRLevels indicator
            self.context.RegisterIndicator(security.Symbol, self.ATRLevels, Resolution.Daily)
            self.context.WarmUpIndicator(security.Symbol, self.ATRLevels, Resolution.Daily)

            # Creating the EMAs
            for period in self.EMAs.keys():
                ema = ExponentialMovingAverage(period)
                self.EMAs[period][security.Symbol] = ema
                self.context.RegisterIndicator(security.Symbol, ema, consolidator15m)
            
            # Creating the Standard Deviation indicator
            # self.stdDevs[security.Symbol] = StandardDeviation(20)
            # self.context.RegisterIndicator(security.Symbol, self.stdDevs[security.Symbol], consolidator5m)

        
        # NOTE: commented out as for some reason in the middle of the backtest SPX is removed from the universe???!
        # for security in changes.RemovedSecurities:
        #     if security.Type != SecurityType.Equity and security.Type != SecurityType.Index:
        #         continue
        #     if security.Symbol not in self.consolidators:
        #         continue
        #     self.context.logger.info(f"Removing consolidator for {security.Symbol}")
        #     consolidator = self.consolidators.pop(security.Symbol)
        #     self.context.SubscriptionManager.RemoveConsolidator(security.Symbol, consolidator)
        #     consolidator.DataConsolidated -= self.onFiveMinuteData

    def handleHODLOD(self, bookPosition, consolidated_bar):
        stats = bookPosition.strategy.stats
        # Get the high/low of the day before the update
        highOfDay = stats.highOfTheDay
        lowOfDay = stats.lowOfTheDay
        # currentDay = self.context.Time.date()   
        
        if bookPosition.orderTag not in self.triggerHODLOD:
            self.triggerHODLOD[bookPosition.orderTag] = RollingWindow[bool](2) # basically wait 25 minutes before triggering

        if bookPosition.strategyId == 'CallCreditSpread' and consolidated_bar.Close > highOfDay:
            self.triggerHODLOD[bookPosition.orderTag].Add(True)
        elif bookPosition.strategyId == "PutCreditSpread" and consolidated_bar.Close < lowOfDay:
            self.triggerHODLOD[bookPosition.orderTag].Add(True)

        if bookPosition.orderTag in self.triggerHODLOD:
            # Check if all values are True and the RollingWindow is full
            if all(self.triggerHODLOD[bookPosition.orderTag]) and self.triggerHODLOD[bookPosition.orderTag].IsReady:
                self.HODLOD[bookPosition.orderTag] = True
        

    def handleFiveMinuteITM(self, bookPosition, consolidated_bar):
        soldLeg = [leg for leg in bookPosition.legs if leg.isSold][0]

        # Check if we should close the position
        if bookPosition.strategyId == 'CallCreditSpread' and consolidated_bar.Close > soldLeg.strike:
            self.fiveMinuteITM[bookPosition.orderTag] = True
        elif bookPosition.strategyId == "PutCreditSpread" and consolidated_bar.Close < soldLeg.strike:
            self.fiveMinuteITM[bookPosition.orderTag] = True
        
