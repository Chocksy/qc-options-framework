#region imports
from AlgorithmImports import *
#endregion

from Initialization import SetupBaseStructure
from Strategy import WorkingOrder
from Tools import Underlying


class Base(RiskManagementModel):
    """
    Manages risk for a trading algorithm by evaluating open positions against risk management criteria such as stop-loss, profit targets,
    and position expiration. Implements the `RiskManagementModel` interface required by QuantConnect.

    Attributes:
        context (object): An object containing contextual information and utility methods for the algorithm.
        DEFAULT_PARAMETERS (dict): Default risk parameters including management frequency, profit targets, and stop-loss multipliers.
    """
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

    def __init__(self, context, strategy_id = 'Base'):
        self.context = context
        self.context.structure.AddConfiguration(parent=self, **self.getMergedParameters())
        self.context.logger.debug(f"{self.__class__.__name__} -> __init__")
        self.context.strategyMonitors[strategy_id] = self

    @classmethod
    def getMergedParameters(cls):
        """
        Merges default parameters with any additional parameters defined in derived classes.

        Returns:
            dict: A dictionary containing the merged parameters.
        """
        return {**cls.DEFAULT_PARAMETERS, **getattr(cls, "PARAMETERS", {})}

    @classmethod
    def parameter(cls, key, default=None):
        """
        Retrieves the value of a parameter by its key, returning a default value if the key is not found.

        Args:
            key (str): The parameter key to retrieve.
            default (any): The default value to return if the key is not found.

        Returns:
            The value of the parameter or the default value if the key is not present.
        """
        return cls.getMergedParameters().get(key, default)

    def ManageRisk(self, algorithm: QCAlgorithm, targets: List[PortfolioTarget]) -> List[PortfolioTarget]:
        """
        Manages the risk of the current open positions and determines which positions, if any, should be closed based on various risk management criteria.

        This method overrides the provided `targets` with a new list of portfolio targets based on the evaluation of current open positions. The method checks the positions against multiple risk thresholds such as stop loss, profit target, DIT/DTE thresholds, expiration date, and custom conditions.
        
        The method follows these steps:
            1. Checks if the current time aligns with the specified schedule (`managePositionFrequency`). If not, it returns an empty list.
            2. Calls `preManageRisk` for any preprocessing required by child classes.
            3. Iterates through all open positions, evaluating each against risk criteria such as stop loss, profit target, DIT/DTE thresholds, expiration date, and custom conditions.
            4. For positions that meet closure criteria, it updates the targets list to close these positions.
            5. Stops the execution timer and returns the updated list of targets.

        Args:
            algorithm (QCAlgorithm): An instance of the base QCAlgorithm class that provides access to the algorithm's state, including portfolio, securities, and time.
            targets (List[PortfolioTarget]): A list of portfolio targets that may be adjusted based on risk management criteria.

        Returns:
            List[PortfolioTarget]: A list of portfolio targets that have been updated based on the risk management assessment. Positions that need to be closed will be included in this list.
        """

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

        # Loop through all open positions
        for orderTag, orderId in list(self.context.openPositions.items()):
            # Skip this contract if in the meantime it has been removed by the onOrderEvent
            if orderTag not in self.context.openPositions:
                continue
            self.context.logger.debug(f"{self.__class__.__name__} -> ManageRisk -> looping through open positions")
            # Get the book position
            bookPosition = self.context.allPositions[orderId]
            # Get the order id
            orderId = bookPosition.orderId
            # Get the order tag
            orderTag = bookPosition.orderTag

            self.context.logger.debug(f"{self.__class__.__name__} -> ManageRisk -> looping through open positions -> orderTag: {orderTag}, orderId: {orderId}")

            # Find the appropriate monitor for this position's strategy
            strategy_monitor = self.context.strategyMonitors.get(bookPosition.strategyId, self.context.strategyMonitors.get('Base'))

            if strategy_monitor: 
                # Method to allow child classes access to the manageRisk method before any changes are made
                strategy_monitor.preManageRisk() 
                self.context.logger.debug(f"{self.__class__.__name__} -> ManageRisk -> preManageRisk")

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

            self.context.logger.debug(f"{self.__class__.__name__} -> ManageRisk -> looping through open positions -> orderTag: {orderTag}, orderId: {orderId} -> bookPosition: {bookPosition}")

            # Special method to monitor the position and handle custom actions on it.
            if strategy_monitor: strategy_monitor.monitorPosition(bookPosition)

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
            shouldCloseFlg = False
            customReasons = None
            if strategy_monitor:
                shouldCloseFlg, customReasons = strategy_monitor.shouldClose(bookPosition)

                if shouldCloseFlg:
                    closeReason.append(customReasons or "It should close from child")

                    # A custom method to handle
                    self.context.logger.debug(f"{self.__class__.__name__} -> ManageRisk -> looping through open positions -> orderTag: {orderTag}, orderId: {orderId} -> shouldCloseFlg: {shouldCloseFlg}, customReasons: {customReasons}")

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

    def preManageRisk(self):
        pass

    def monitorPosition(self, position):
        pass

    def shouldClose(self, position):
        return False, None

    def checkMarketCloseCutoffDttm(self, position):
        if position.strategyParam('marketCloseCutoffTime') != None:
            return self.context.Time >= position.expiryMarketCloseCutoffDttm(self.context)
        else:
            return False

    def checkStopLoss(self, position):
        """
        Evaluates if a position has hit its stop loss threshold and needs to be closed.

        Args:
            position: The position to evaluate.

        Returns:
            bool: True if the stop loss condition is met, False otherwise.
        """
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
        """
        Determines if a position has reached its profit target and can be closed.

        Args:
            position: The position to check.

        Returns:
            bool: True if the profit target is met, False otherwise.
        """
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
        """
        Checks if the position has been held longer than the allowed Days in Trade (DIT) threshold.

        Args:
            position: The position to evaluate.

        Returns:
            tuple: A tuple containing two booleans (hardDitStopFlg, softDitStopFlg) indicating if the hard or soft DIT thresholds have been met.
        """
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
        """
        Checks if the position is approaching or has reached its Days to Expiration (DTE) threshold and needs to be closed.

        Args:
            position: The position to evaluate.

        Returns:
            tuple: A tuple containing two booleans (hardDteStopFlg, softDteStopFlg) indicating if the hard or soft DTE thresholds have been met.
        """
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
        """
        Verifies if the current simulation time has reached or passed the designated end time for the backtest.

        Returns:
            bool: True if the current time has reached or exceeded the end of backtest time, False otherwise.
        """
        if self.context.endOfBacktestCutoffDttm is not None and self.context.Time >= self.context.endOfBacktestCutoffDttm:
            return True
        return False

    def closePosition(self, position, closeReason, stopLossFlg=False):
        """
        Closes a position based on specific criteria or conditions, such as hitting a stop loss or reaching a profit target.

        Args:
            position: The position to close.
            closeReason: The reason for closing the position.
            stopLossFlg: A flag indicating if the position is being closed due to a stop loss.

        Returns:
            list: A list of new or modified portfolio targets as a result of closing the position.
        """
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
            

