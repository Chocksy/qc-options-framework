#region imports
from AlgorithmImports import *
#endregion

from Initialization import SetupBaseStructure
from Strategy import WorkingOrder
from Tools import Underlying


class Base(RiskManagementModel):
    DEFAULT_PARAMETERS = {
        # The frequency (in minutes) with which each position is managed
        "managePositionFrequency": 1,
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        "profitTarget": 0.8,
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
        self.context = context
        self.context.structure.AddConfiguration(parent=self, **self.getMergedParameters())
        self.context.logger.debug(f"{self.__class__.__name__} -> __init__")

    @classmethod
    def getMergedParameters(cls):
        # Merge the DEFAULT_PARAMETERS from both classes
        return {**cls.DEFAULT_PARAMETERS, **getattr(cls, "PARAMETERS", {})}

    @classmethod
    def parameter(cls, key, default=None):
        return cls.getMergedParameters().get(key, default)

    # @param algorithm [QCAlgorithm] The algorithm argument that the methods receive is an instance of the base QCAlgorithm class, not your subclass of it.
    # @param targets [List[PortfolioTarget]] The list of targets to be ordered
    def ManageRisk(self, algorithm: QCAlgorithm, targets: List[PortfolioTarget]) -> List[PortfolioTarget]:
        # Start the timer
        self.context.executionTimer.start('Monitor.Base -> ManageRisk')
        # We are basically ignoring the current portfolio targets to be assessed for risk
        # and building our own based on the current open positions
        targets = []
        self.context.logger.debug(f"{self.__class__.__name__} -> ManageRisk -> start")
        managePositionFrequency = max(self.managePositionFrequency, 1)

        # Continue the processing only if we are at the specified schedule
        if self.context.Time.minute % managePositionFrequency != 0:
            return []

        # Method to allow child classes access to the manageRisk method before any changes are made
        self.preManageRisk()
        self.context.Log(f"{self.__class__.__name__} -> ManageRisk -> preManageRisk")
        # Loop through all open positions
        for orderTag, orderId in list(self.context.openPositions.items()):
            # Skip this contract if in the meantime it has been removed by the onOrderEvent
            if orderTag not in self.context.openPositions:
                continue

            # Get the book position
            bookPosition = self.context.allPositions[orderId]
            # Get the order id
            orderId = bookPosition.orderId
            # Get the order tag
            orderTag = bookPosition.orderTag

            # Check if this is a fully filled position
            if bookPosition.openOrder.filled is False:
                continue

            # Possible Scenarios:
            #   - Credit Strategy:
            #        -> openPremium > 0
            #        -> profitTarget <= 1
            #        -> stopLossMultiplier >= 1
            #        -> maxLoss = Depending on the strategy
            #   - Debit Strategy:
            #        -> openPremium < 0
            #        -> profitTarget >= 0
            #        -> stopLossMultiplier <= 1
            #        -> maxLoss = openPremium

            # Get the current value of the position
            bookPosition.getPositionValue(self.context)
            # Extract the positionPnL (per share)
            positionPnL = bookPosition.positionPnL

            # Exit if the positionPnL is not available (bid-ask spread is too wide)
            if positionPnL is None:
                return []

            bookPosition.updatePnLRange(self.context.Time.date(), positionPnL)

            # Special method to monitor the position and handle custom actions on it.
            self.monitorPosition(bookPosition)

            # Initialize the closeReason
            closeReason = []

            # Check if we've hit the stop loss threshold
            stopLossFlg = self.checkStopLoss(bookPosition)
            if stopLossFlg:
                closeReason.append("Stop Loss trigger")

            profitTargetFlg = self.checkProfitTarget(bookPosition)
            if profitTargetFlg:
                closeReason.append("Profit target")

            # Check if we've hit the Dit threshold
            hardDitStopFlg, softDitStopFlg = self.checkDitThreshold(bookPosition)
            if hardDitStopFlg:
                closeReason.append("Hard Dit cutoff")
            elif softDitStopFlg:
                closeReason.append("Soft Dit cutoff")

            # Check if we've hit the Dte threshold
            hardDteStopFlg, softDteStopFlg = self.checkDteThreshold(bookPosition)
            if hardDteStopFlg:
                closeReason.append("Hard Dte cutoff")
            elif softDteStopFlg:
                closeReason.append("Soft Dte cutoff")

            # Check if this is the last trading day before expiration and we have reached the cutoff time
            expiryCutoffFlg = self.checkMarketCloseCutoffDttm(bookPosition)
            if expiryCutoffFlg:
                closeReason.append("Expiration date cutoff")

            # Check if this is the last trading day before expiration and we have reached the cutoff time
            endOfBacktestCutoffFlg = self.checkEndOfBacktest()
            if endOfBacktestCutoffFlg:
                closeReason.append("End of backtest cutoff")
                # Set the stopLossFlg = True to force a Market Order
                stopLossFlg = True

            # Check any custom condition from the strategy to determine closure.
            shouldCloseFlg, customReasons = self.shouldClose(bookPosition)
            if shouldCloseFlg:
                closeReason.append(customReasons or "It should close from child")

            # A custom method to handle

            # Update the stats of each contract
            # TODO: add back this section
            # if self.strategyParam("includeLegDetails") and self.context.Time.minute % self.strategyParam("legDatailsUpdateFrequency") == 0:
            #     for contract in position["contracts"]:
            #         self.updateContractStats(bookPosition, position, contract)
            #     if self.strategyParam("trackLegDetails"):
            #         underlyingPrice = self.context.GetLastKnownPrice(self.context.Securities[self.context.underlyingSymbol]).Price
            #         self.context.positionTracking[orderId][self.context.Time][f"{self.name}.underlyingPrice"] = underlyingPrice
            #         self.context.positionTracking[orderId][self.context.Time][f"{self.name}.PnL"] = positionPnL

            # Check if we need to close the position
            if (
                profitTargetFlg  # We hit the profit target
                or stopLossFlg  # We hit the stop loss (making sure we don't exceed the max loss in case of spreads)
                or hardDteStopFlg  # The position must be closed when reaching the DTE threshold (hard stop)
                or softDteStopFlg  # Soft DTE stop: close as soon as it is profitable
                or hardDitStopFlg  # The position must be closed when reaching the DIT threshold (hard stop)
                or softDitStopFlg  # Soft DIT stop: close as soon as it is profitable
                or expiryCutoffFlg  # This is the last trading day before expiration, we have reached the cutoff time
                or endOfBacktestCutoffFlg  # This is the last trading day before the end of the backtest -> Liquidate all positions
                or shouldCloseFlg # This will be the flag that is defined by the child classes of monitor
            ):
                # Close the position
                targets = self.closePosition(bookPosition, closeReason, stopLossFlg=stopLossFlg)

        # Stop the timer
        self.context.executionTimer.stop('Monitor.Base -> ManageRisk')

        return targets

    """
    Method to allow child classes access to the manageRisk method before any changes are made
    """
    def preManageRisk(self):
        pass

    """
    Special method to monitor the position and handle custom actions on it.
    These actions can be:
    - add a working order to open a hedge position to defend the current one
    - add a working order to increase the size of the position to improve avg price
    """
    def monitorPosition(self, position):
        pass

    """
    Another special method that should be ovewritten by child classes.
    This method can look for indicators or other decisions to close the position.
    """
    def shouldClose(self, position):
        pass

    def checkMarketCloseCutoffDttm(self, position):
        if position.strategyParam('marketCloseCutoffTime') != None:
            return self.context.Time >= position.expiryMarketCloseCutoffDttm(self.context)
        else:
            return False

    def checkStopLoss(self, position):
        # Get the Stop Loss multiplier
        stopLossMultiplier = self.stopLossMultiplier
        capStopLoss = self.capStopLoss

        # Get the amount of credit received to open the position
        openPremium = position.openOrder.premium
        # Get the quantity used to open the position
        positionQuantity = position.orderQuantity
        # Maximum Loss (pre-computed at the time of creating the order)
        maxLoss = position.openOrder.maxLoss * positionQuantity
        if capStopLoss:
            # Add the premium to compute the net loss
            netMaxLoss = maxLoss + openPremium
        else:
            netMaxLoss = float("-Inf")

        stopLoss = None
        # Check if we are using a stop loss
        if stopLossMultiplier is not None:
            # Set the stop loss amount
            stopLoss = -abs(openPremium) * stopLossMultiplier

        # Extract the positionPnL (per share)
        positionPnL = position.positionPnL

        # Tolerance level, e.g., 0.05 for 5%
        tolerance = 0.05

        # Check if we've hit the stop loss threshold or are within the tolerance range
        stopLossFlg = False
        if stopLoss is not None and (netMaxLoss <= positionPnL <= stopLoss or netMaxLoss <= positionPnL <= stopLoss * (1 + tolerance)):
            stopLossFlg = True

        # Keep track of the midPrices of this order for faster debugging
        position.priceProgressList.append(round(position.orderMidPrice, 2))

        return stopLossFlg

    def checkProfitTarget(self, position):
        # Get the amount of credit received to open the position
        openPremium = position.openOrder.premium
        # Extract the positionPnL (per share)
        positionPnL = position.positionPnL

        # Get the target profit amount (if it has been set at the time of creating the order)
        targetProfit = position.targetProfit
        # Set the target profit amount if the above step returned no value
        if targetProfit is None and self.profitTarget is not None:
            targetProfit = abs(openPremium) * self.profitTarget

        # Tolerance level, e.g., 0.05 for 5%
        tolerance = 0.05

        # Check if we hit the profit target or are within the tolerance range
        profitTargetFlg = False
        if targetProfit is not None and (positionPnL >= targetProfit or positionPnL >= targetProfit * (1 - tolerance)):
            profitTargetFlg = True

        return profitTargetFlg


    def checkDitThreshold(self, position):
        # Get the book position
        bookPosition = self.context.allPositions[position.orderId]
        # How many days has this position been in trade for
        currentDit = (self.context.Time.date() - bookPosition.openFilledDttm.date()).days

        hardDitStopFlg = False
        softDitStopFlg = False

        # Extract the positionPnL (per share)
        positionPnL = position.positionPnL

        # Check for DTE stop
        if (
            position.strategyParam("ditThreshold") is not None  # The ditThreshold has been specified
            and position.strategyParam("dte") > position.strategyParam("ditThreshold")  # We are using the ditThreshold only if the open DTE was larger than the threshold
            and currentDit >= position.strategyParam("ditThreshold")  # We have reached the DTE threshold
        ):
            # Check if this is a hard DTE cutoff
            if (
                position.strategyParam("forceDitThreshold") is True
                or (position.strategyParam("hardDitThreshold") is not None and currentDit >= position.strategyParam("hardDitThreshold"))
            ):
                hardDitStopFlg = True
                # closeReason = closeReason or "Hard DIT cutoff"
            # Check if this is a soft DTE cutoff
            elif positionPnL >= 0:
                softDitStopFlg = True
                # closeReason = closeReason or "Soft DIT cutoff"

        return hardDitStopFlg, softDitStopFlg

    def checkDteThreshold(self, position):
        hardDteStopFlg = False
        softDteStopFlg = False
        # Extract the positionPnL (per share)
        positionPnL = position.positionPnL
        # How many days to expiration are left for this position
        currentDte = (position.expiry.date() - self.context.Time.date()).days
        # Check for DTE stop
        if (
            position.strategyParam("dteThreshold") is not None  # The dteThreshold has been specified
            and position.strategyParam("dte") > position.strategyParam("dteThreshold")  # We are using the dteThreshold only if the open DTE was larger than the threshold
            and currentDte <= position.strategyParam("dteThreshold")  # We have reached the DTE threshold
        ):
            # Check if this is a hard DTE cutoff
            if position.strategyParam("forceDteThreshold") is True:
                hardDteStopFlg = True
                # closeReason = closeReason or "Hard DTE cutoff"
            # Check if this is a soft DTE cutoff
            elif positionPnL >= 0:
                softDteStopFlg = True
                # closeReason = closeReason or "Soft DTE cutoff"

        return hardDteStopFlg, softDteStopFlg

    def checkEndOfBacktest(self):
        if self.context.endOfBacktestCutoffDttm is not None and self.context.Time >= self.context.endOfBacktestCutoffDttm:
            return True
        return False

    def closePosition(self, position, closeReason, stopLossFlg=False):
        # Start the timer
        self.context.executionTimer.start()

        targets = []

        # Get the context
        context = self.context
        # Get the strategy parameters
        # parameters = self.parameters

        # Get Order Id and expiration
        orderId = position.orderId
        # expiryStr = position.expiryStr
        orderTag = position.orderTag
        orderMidPrice = position.orderMidPrice
        limitOrderPrice = position.limitOrderPrice
        bidAskSpread = position.bidAskSpread

        # Get the details currently open position
        openPosition = context.openPositions[orderTag]
        # Get the book position
        bookPosition = context.allPositions[orderId]
        # Get the last trading day before expiration
        expiryLastTradingDay = bookPosition.expiryLastTradingDay(context)
        # Get the date/time threshold by which the position must be closed (on the last trading day before expiration)
        expiryMarketCloseCutoffDttm = None
        if bookPosition.strategyParam("marketCloseCutoffTime") != None:
            expiryMarketCloseCutoffDttm = bookPosition.expiryMarketCloseCutoffDttm(context)

        # Get the contracts and their side
        contracts = [l.contract for l in bookPosition.legs]
        contractSide = bookPosition.contractSide
        # Set the expiration threshold at 15:40 of the expiration date (but no later than the market close cut-off time).
        expirationThreshold = None
        if expiryMarketCloseCutoffDttm != None:
            expirationThreshold = min(expiryLastTradingDay + timedelta(hours=15, minutes=40), expiryMarketCloseCutoffDttm + bookPosition.strategyParam("limitOrderExpiration"))
            # Set the expiration date for the Limit order. Make sure it does not exceed the expiration threshold
            limitOrderExpiryDttm = min(context.Time + bookPosition.strategyParam("limitOrderExpiration"), expirationThreshold)
        else:
            limitOrderExpiryDttm = min(context.Time + bookPosition.strategyParam("limitOrderExpiration"), expiryLastTradingDay + timedelta(hours=15, minutes=40))

        # Determine if we are going to use a Limit Order
        useLimitOrders = (
            # Check if we are supposed to use Limit orders as a default
            bookPosition.strategyParam("useLimitOrders")
            # Make sure there is enough time left to expiration.
            # Once we cross the expiration threshold (10 minutes from market close on the expiration day) we are going to submit a Market order
            and (expirationThreshold is None or context.Time <= expirationThreshold)
            # It's not a stop loss (stop losses are executed through a Market order)
            and not stopLossFlg
        )
        # Determine if we are going to use a Market Order
        useMarketOrders = not useLimitOrders

        # Get the price of the underlying at the time of closing the position
        priceAtClose = None
        if context.Securities.ContainsKey(bookPosition.underlyingSymbol()):
            if context.Securities[bookPosition.underlyingSymbol()] is not None:
                priceAtClose = context.Securities[bookPosition.underlyingSymbol()].Close
            else:
                self.context.logger.warning("priceAtClose is None")

        # Set the midPrice for the order to close
        bookPosition.closeOrder.orderMidPrice = orderMidPrice
        # Set the Limit order expiration.
        bookPosition.closeOrder.limitOrderExpiryDttm = limitOrderExpiryDttm

        # Set the timestamp when the closing order is created
        bookPosition.closeDttm = context.Time
        # Set the date when the closing order is created
        bookPosition.closeDt = context.Time.strftime("%Y-%m-%d")
        # Set the price of the underlying at the time of submitting the order to close
        bookPosition.underlyingPriceAtOrderClose = priceAtClose
        # Set the price of the underlying at the time of submitting the order to close:
        # - This is the same as underlyingPriceAtOrderClose in case of Market Orders
        # - In case of Limit orders, this is the actual price of the underlying at the time when the Limit Order was triggered (price is updated later by the manageLimitOrders method)
        bookPosition.underlyingPriceAtClose = priceAtClose
        # Set the mid-price of the position at the time of closing
        bookPosition.closeOrderMidPrice = orderMidPrice
        bookPosition.closeOrderMidPriceMin = orderMidPrice
        bookPosition.closeOrderMidPriceMax = orderMidPrice
        # Set the Limit Order price of the position at the time of closing
        bookPosition.closeOrderLimitPrice = limitOrderPrice
        bookPosition.closeOrder.limitOrderPrice = limitOrderPrice
        # Set the close DTE
        bookPosition.closeDTE = (bookPosition.expiry.date() - context.Time.date()).days
        # Set the Days in Trade
        bookPosition.DIT = (context.Time.date() - bookPosition.openFilledDttm.date()).days
        # Set the close reason
        bookPosition.closeReason = closeReason

        if useMarketOrders:
            # Log the parameters used to validate the order
            self.context.logger.debug("Executing Market Order to close the position:")
            self.context.logger.debug(f" - orderTag: {orderTag}")
            self.context.logger.debug(f" - strikes: {[c.Strike for c in contracts]}")
            self.context.logger.debug(f" - orderQuantity: {bookPosition.orderQuantity}")
            self.context.logger.debug(f" - midPrice: {orderMidPrice}")
            self.context.logger.debug(f" - bidAskSpread: {bidAskSpread}")
            self.context.logger.debug(f" - closeReason: {closeReason}")
            # Store the Bid-Ask spread at the time of executing the order
            bookPosition["closeOrderBidAskSpread"] = bidAskSpread

        # legs = []
        # isComboOrder = len(contracts) > 1

        if useMarketOrders:
            position.limitOrder = False
        elif useLimitOrders:
            position.limitOrder = True

        for leg in position.legs:
            # Extract order parameters
            symbol = leg.symbol
            orderSide = leg.orderSide
            # orderQuantity = leg.orderQuantity

            # TODO: I'm not sure about this order side check here
            if orderSide != 0:
                targets.append(PortfolioTarget(symbol, orderSide))

        # Submit the close orders
        context.workingOrders[orderTag] = WorkingOrder(
            targets=targets,
            orderId=orderId,
            useLimitOrder=useLimitOrders,
            limitOrderPrice=limitOrderPrice,
            orderType="close",
            fills=0
        )

        # Stop the timer
        context.executionTimer.stop()
        return targets

    # Optional: Be notified when securities change
    def OnSecuritiesChanged(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        pass
            

