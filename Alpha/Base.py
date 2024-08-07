#region imports
from AlgorithmImports import *
#endregion

from Initialization import SetupBaseStructure
from Alpha.Utils import Scanner, Order, Stats
from Tools import ContractUtils, Logger, Underlying
from Strategy import Leg, Position, OrderType, WorkingOrder

"""
NOTE: We can't use multiple inheritance in Python because this is a managed class. We will use composition instead so in
      order to call the methods of SetupBaseStructure we'll call then using self.setup.methodName().
----------------------------------------------------------------------------------------------------------------------------------------
The base class for all the alpha models. It is used to setup the base structure of the algorithm and to run the strategies.
This class has some configuration capabilities that can be used to setup the strategies more easily by just changing the
configuration parameters.

Here are the default values for the configuration parameters:

    scheduleStartTime: time(9, 30, 0)
    scheduleStopTime: None
    scheduleFrequency: timedelta(minutes = 5)
    maxActivePositions: 1
    dte: 0
    dteWindow: 0

----------------------------------------------------------------------------------------------------------------------------------------
The workflow of the algorithm is the following:

    `Update` method gets called every minute
        - If the market is closed, the algorithm exits
        - If algorithm is warming up, the algorithm exits
        - The Scanner class is used to filter the option chain
            - If the chain is empty, the algorithm exits
        - The CreateInsights method is called
            - Inside the GetOrder method is called
"""


class Base(AlphaModel):
    # Internal counter for all the orders
    orderCount = 0

    DEFAULT_PARAMETERS = {
        # The start time at which the algorithm will start scheduling the strategy execution
        # (to open new positions). No positions will be opened before this time
        "scheduleStartTime": time(9, 30, 0),
        # The stop time at which the algorithm will look to open a new position.
        "scheduleStopTime": None,  # time(13, 0, 0),
        # Periodic interval with which the algorithm will check to open new positions
        "scheduleFrequency": timedelta(minutes=5),
        # Minimum time distance between opening two consecutive trades
        "minimumTradeScheduleDistance": timedelta(days=1),
        # If True, the order is not placed if the legs are already part of an existing position.
        "checkForDuplicatePositions": True,
        # Maximum number of open positions at any given time
        "maxActivePositions": 1,
        # Maximum quantity used to scale each position. If the target premium cannot be reached within this
        # quantity (i.e. premium received is too low), the position is not going to be opened
        "maxOrderQuantity": 1,
        # If True, the order is submitted as long as it does not exceed the maxOrderQuantity.
        "validateQuantity": True,
        # Days to Expiration
        "dte": 0,
        # The size of the window used to filter the option chain: options expiring in the range [dte-dteWindow, dte] will be selected
        "dteWindow": 0,
        # DTE Threshold. This is ignored if self.dte < self.dteThreshold
        "dteThreshold": 21,
        # Controls whether to use the furthest (True) or the earliest (False) expiration date when multiple expirations are available in the chain
        "useFurthestExpiry": True,
        # Controls whether to consider the DTE of the last closed position when opening a new one:
        # If True, the Expiry date of the new position is selected such that the open DTE is the nearest to the DTE of the closed position
        "dynamicDTESelection": False,
        # Coarse filter for the Universe selection. It selects nStrikes on both sides of the ATM strike for each available expiration
        "nStrikesLeft": 200,   # 200 SPX @ 3820 & 3910C w delta @ 1.95 => 90/5 = 18
        "nStrikesRight": 200,   # 200
        # Controls what happens when an open position reaches/crosses the dteThreshold ( -> DTE(openPosition) <= dteThreshold)
        # - If True, the position is closed as soon as the dteThreshold is reached, regardless of whether the position is profitable or not
        # - If False, once the dteThreshold is reached, the position is closed as soon as it is profitable
        "forceDteThreshold": False,
        # DIT Threshold. This is ignored if self.dte < self.ditThreshold
        "ditThreshold": None,
        "hardDitThreshold": None,
        # Controls what happens when an open position reaches/crosses the ditThreshold ( -> DIT(openPosition) >= ditThreshold)
        # - If True, the position is closed as soon as the ditThreshold is reached, regardless of whether the position is profitable or not
        # - If False, once the ditThreshold is reached, the position is closed as soon as it is profitable
        # - If self.hardDitThreashold is set, the position is closed once the hardDitThreashold is
        # crossed, regardless of whether forceDitThreshold is True or False
        "forceDitThreshold": False,
        # Slippage used to set Limit orders
        "slippage": 0.0,
        # Used when validateBidAskSpread = True. if the ratio between the bid-ask spread and the
        # mid-price is higher than this parameter, the order is not executed
        "bidAskSpreadRatio": 0.3,
        # If True, the order mid-price is validated to make sure the Bid-Ask spread is not too wide.
        #  - The order is not submitted if the ratio between Bid-Ask spread of the entire order and its mid-price is more than self.bidAskSpreadRatio
        "validateBidAskSpread": False,
        # Control whether to allow multiple positions to be opened for the same Expiration date
        "allowMultipleEntriesPerExpiry": False,
        # Controls whether to include details on each leg (open/close fill price and descriptive statistics about mid-price, Greeks, and IV)
        "includeLegDetails": False,
        # The frequency (in minutes) with which the leg details are updated (used only if includeLegDetails = True)
        "legDatailsUpdateFrequency": 30,
        # Controls whether to track the details on each leg across the life of the trade
        "trackLegDetails": False,
        # Controls which greeks are included in the output log
        # "greeksIncluded": ["Delta", "Gamma", "Vega", "Theta", "Rho", "Vomma", "Elasticity"],
        "greeksIncluded": [],
        # Controls whether to compute the greeks for the strategy. If True, the greeks will be computed and stored in the contract under BSMGreeks.
        "computeGreeks": False,
        # The time (on expiration day) at which any position that is still open will closed
        "marketCloseCutoffTime": time(15, 45, 0),
        # Limit Order Management
        "useLimitOrders": True,
        # Adjustment factor applied to the Mid-Price to set the Limit Order:
        #  - Credit Strategy:
        #      Adj = 0.3 --> sets the Limit Order price 30% higher than the current Mid-Price
        #  - Debit Strategy:
        #      Adj = -0.2 --> sets the Limit Order price 20% lower than the current Mid-Price
        "limitOrderRelativePriceAdjustment": 0,
        # Set expiration for Limit orders. This tells us how much time a limit order will stay in pending mode before it gets a fill.
        "limitOrderExpiration": timedelta(hours=8),
        # Alternative method to set the absolute price (per contract) of the Limit Order. This method is used if a number is specified
        # Unless you know that your price target can get a fill, it is advisable to use a relative adjustment or you may never get your order filled
        #  - Credit Strategy:
        #      AbsolutePrice = 1.5 --> sets the Limit Order price at exactly 1.5$
        #  - Debit Strategy:
        #      AbsolutePrice = -2.3 --> sets the Limit Order price at exactly -2.3$
        "limitOrderAbsolutePrice": None,
        # Target <credit|debit> premium amount: used to determine the number of contracts needed to reach the desired target amount
        #  - targetPremiumPct --> target premium is expressed as a percentage of the total Portfolio Net Liq (0 < targetPremiumPct < 1)
        #  - targetPremium --> target premium is a fixed dollar amount
        # If both are specified, targetPremiumPct takes precedence. If none of them are specified,
        # the number of contracts specified by the maxOrderQuantity parameter is used.
        "targetPremiumPct": None,
        # You can't have one without the other in this case below.
        # Minimum premium accepted for opening a new position. Setting this to None disables it.
        "minPremium": None,
        # Maximum premium accepted for opening a new position. Setting this to None disables it.
        "maxPremium": None,
        "targetPremium": None,
        # Defines how the profit target is calculated. Valid options are (case insensitive):
        # - Premium: the profit target is a percentage of the premium paid/received.
        # - Theta: the profit target is calculated based on the theta value of the position evaluated
        # at self.thetaProfitDays from the time of entering the trade
        # - TReg: the profit target is calculated as a percentage of the TReg (MaxLoss + openPremium)
        # - Margin: the profit target is calculted as a percentage of the margin requirement (calculated based on
        # self.portfolioMarginStress percentage upside/downside movement of the underlying)
        "profitTargetMethod": "Premium",
        # Profit Target Factor (Multiplier of the premium received/paid when the position was opened)
        "profitTarget": 0.6,
        # Number of days into the future at which the theta of the position is calculated. Used if profitTargetMethod = "Theta"
        "thetaProfitDays": None,
        # Delta and Wing size used for Naked Put/Call and Spreads
        "delta": 10,
        "wingSize": 10,
        # Put/Call delta for Iron Condor
        "putDelta": 10,
        "callDelta": 10,
        # Net delta for Straddle, Iron Fly and Butterfly (using ATM strike if netDelta = None)
        "netDelta": None,
        # Put/Call Wing size for Iron Condor, Iron Fly
        "putWingSize": 10,
        "callWingSize": 10,
        # Butterfly specific parameters
        "butteflyType": None,
        "butterflyLeftWingSize": 10,
        "butterflyRightWingSize": 10,
        # useSlice determines if we should use the chainOption slice data instead of optionProvider. Default is set to FALSE
        "useSlice": False,
    }

    def __init__(self, context):
        self.context = context
        # Set default name (use the class name)
        self.name = type(self).__name__
        # Set the Strategy Name (optional)
        self.nameTag = self.name
        # Set the logger
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)
        self.order = Order(context, self)
        # This adds all the parameters to the class. We can also access them via self.parameter("parameterName")
        self.context.structure.AddConfiguration(parent=self, **self.getMergedParameters())
        # Initialize the contract utils
        self.contractUtils = ContractUtils(context)
        # Initialize the stats dictionary
        # This will hold any details related to the underlying.
        # For example, the underlying price at the time of opening of day
        self.stats = Stats()
        self.logger.debug(f'{self.name} -> __init__')

    @staticmethod
    def getNextOrderId():
        Base.orderCount += 1
        return Base.orderCount

    @classmethod
    def getMergedParameters(cls):
        # Merge the DEFAULT_PARAMETERS from both classes
        return {**cls.DEFAULT_PARAMETERS, **getattr(cls, "PARAMETERS", {})}

    @classmethod
    def parameter(cls, key, default=None):
        return cls.getMergedParameters().get(key, default)

    def update(self, algorithm: QCAlgorithm, data: Slice) -> List[Insight]:
        insights = []
        # Start the timer
        self.context.executionTimer.start('Alpha.Base -> Update')
        self.logger.debug(f'{self.name} -> update -> start')
        self.logger.debug(f'Is Warming Up: {self.context.IsWarmingUp}')
        self.logger.debug(f'Is Market Open: {self.context.IsMarketOpen(self.underlyingSymbol)}')
        self.logger.debug(f'Time: {self.context.Time}')
        # Exit if the algorithm is warming up or the market is closed (avoid processing orders on the last minute as these will be executed the following day)
        if self.context.IsWarmingUp or\
           not self.context.IsMarketOpen(self.underlyingSymbol) or\
           self.context.Time.time() >= time(16, 0, 0):
            return insights
        
        self.logger.debug(f'Did Alpha UPDATE after warmup?!?')
        # This thing just passes the data to the performance tool so we can keep track of all 
        # symbols. This should not be needed if the culprit of the slonwess of backtesting is sorted.
        self.context.performance.OnUpdate(data)

        # Update the stats dictionary
        self.syncStats()

        # Check if the workingOrders are still OK to execute
        self.context.structure.checkOpenPositions()

        # Run the strategies to open new positions
        filteredChain, lastClosedOrderTag = Scanner(self.context, self).Call(data)

        self.logger.debug(f'Did Alpha SCAN')
        self.logger.debug(f'Last Closed Order Tag: {lastClosedOrderTag}')
        if filteredChain is not None:
            if self.stats.hasOptions == False:
                self.logger.info(f"Found options {self.context.Time.strftime('%A, %Y-%m-%d %H:%M')}")
            self.stats.hasOptions = True
            insights = self.CreateInsights(filteredChain, lastClosedOrderTag, data)
        elif self.stats.hasOptions is None and self.context.Time.time() >= time(9, 35, 0):
            self.stats.hasOptions = False
            self.logger.info(f"No options data for {self.context.Time.strftime('%A, %Y-%m-%d %H:%M')}")
            self.logger.debug(f"NOTE: Why could this happen? A: The filtering of the chain caused no contracts to be returned. Make sure to make a check on this.")

        # Stop the timer
        self.context.executionTimer.stop('Alpha.Base -> Update')
        return Insight.Group(insights)

    # Get the order with extra filters applied by the strategy
    def GetOrder(self, chain):
        raise NotImplementedError("GetOrder() not implemented")

    # Previous method CreateOptionPosition.py#OpenPosition
    def CreateInsights(self, chain, lastClosedOrderTag=None, data = Slice) -> List[Insight]:
        insights = []
        # Call the getOrder method of the class implementing OptionStrategy
        order = self.getOrder(chain, data)
        # Execute the order
        # Exit if there is no order to process
        if order is None:
            return insights

        # Start the timer
        self.context.executionTimer.start('Alpha.Base -> CreateInsights')

        # Get the context
        context = self.context

        order = [order] if not isinstance(order, list) else order
        for o in order:
            self.logger.debug(f"CreateInsights -> strategyId: {o['strategyId']}, strikes: {o['strikes']}")

        for single_order in order:
            position, workingOrder = self.buildOrderPosition(single_order, lastClosedOrderTag)
            self.logger.debug(f"CreateInsights -> position: {position}")
            self.logger.debug(f"CreateInsights -> workingOrder: {workingOrder}")
            if position is None:
                continue

            if self.hasDuplicateLegs(single_order):
                self.logger.debug(f"CreateInsights -> Duplicate legs found in order: {single_order}")
                continue

            orderId = position.orderId
            orderTag = position.orderTag
            insights.extend(workingOrder.insights)

            # Add this position to the global dictionary
            context.allPositions[orderId] = position
            context.openPositions[orderTag] = orderId

            # Keep track of all the working orders
            context.workingOrders[orderTag] = {}

            # Map each contract to the openPosition dictionary (key: expiryStr)
            context.workingOrders[orderTag] = workingOrder

        self.logger.debug(f"CreateInsights -> insights: {insights}")
        # Stop the timer
        self.context.executionTimer.stop('Alpha.Base -> CreateInsights')
        return insights

    def buildOrderPosition(self, order, lastClosedOrderTag=None):
        # Get the context
        context = self.context

        # Get the list of contracts
        contracts = order["contracts"]
        self.logger.debug(f"buildOrderPosition -> contracts: {len(contracts)}")
        # Exit if there are no contracts
        if (len(contracts) == 0):
            return [None, None]

        useLimitOrders = self.useLimitOrders
        useMarketOrders = not useLimitOrders

        # Current timestamp
        currentDttm = self.context.Time

        strategyId = order["strategyId"]
        contractSide = order["contractSide"]
        # midPrices = order["midPrices"]
        strikes = order["strikes"]
        # IVs = order["IV"]
        expiry = order["expiry"]
        targetPremium = order["targetPremium"]
        maxOrderQuantity = order["maxOrderQuantity"]
        orderQuantity = order["orderQuantity"]
        bidAskSpread = order["bidAskSpread"]
        orderMidPrice = order["orderMidPrice"]
        limitOrderPrice = order["limitOrderPrice"]
        maxLoss = order["maxLoss"]
        targetProfit = order.get("targetProfit", None)

        # Expiry String
        expiryStr = expiry.strftime("%Y-%m-%d")

        self.logger.debug(f"buildOrderPosition -> expiry: {expiry}, expiryStr: {expiryStr}")

        # Validate the order prior to submit
        if (  # We have a minimum order quantity
                orderQuantity == 0
                # The sign of orderMidPrice must be consistent with whether this is a credit strategy (+1) or debit strategy (-1)
                or np.sign(orderMidPrice) != 2 * int(order["creditStrategy"]) - 1
                # Exit if the order quantity exceeds the maxOrderQuantity
                or (self.validateQuantity and orderQuantity > maxOrderQuantity)
                # Make sure the bid-ask spread is not too wide before opening the position.
                # Only for Market orders. In case of limit orders, this validation is done at the time of execution of the Limit order
                or (useMarketOrders and self.validateBidAskSpread
                    and abs(bidAskSpread) >
                    self.bidAskSpreadRatio * abs(orderMidPrice))):
            return [None, None]

        self.logger.debug(f"buildOrderPosition -> orderMidPrice: {orderMidPrice}, orderQuantity: {orderQuantity}, maxOrderQuantity: {maxOrderQuantity}")

        # Get the current price of the underlying
        underlyingPrice = self.contractUtils.getUnderlyingLastPrice(contracts[0])

        # Get the Order Id and add it to the order dictionary
        orderId = self.getNextOrderId()
        # Create unique Tag to keep track of the order when the fill occurs
        orderTag = f"{strategyId}-{orderId}"

        strategyLegs = []
        self.logger.debug(f"buildOrderPosition -> strategyLegs: {strategyLegs}")
        for contract in contracts:
            key = order["contractSideDesc"][contract.Symbol]
            leg = Leg(
                key=key,
                strike=strikes[key],
                expiry=order["contractExpiry"][key],
                contractSide=contractSide[contract.Symbol],
                symbol=contract.Symbol,
                contract=contract,
            )

            strategyLegs.append(leg)

        position = Position(
            orderId=orderId,
            orderTag=orderTag,
            strategy=self,
            strategyTag=self.nameTag,
            strategyId=strategyId,
            legs=strategyLegs,
            expiry=expiry,
            expiryStr=expiryStr,
            targetProfit=targetProfit,
            linkedOrderTag=lastClosedOrderTag,
            contractSide=contractSide,
            openDttm=currentDttm,
            openDt=currentDttm.strftime("%Y-%m-%d"),
            openDTE=(expiry.date() - currentDttm.date()).days,
            limitOrder=useLimitOrders,
            targetPremium=targetPremium,
            orderQuantity=orderQuantity,
            maxOrderQuantity=maxOrderQuantity,
            openOrderMidPrice=orderMidPrice,
            openOrderMidPriceMin=orderMidPrice,
            openOrderMidPriceMax=orderMidPrice,
            openOrderBidAskSpread=bidAskSpread,
            openOrderLimitPrice=limitOrderPrice,
            # underlyingPriceAtOrderOpen=underlyingPrice,
            underlyingPriceAtOpen=underlyingPrice,
            openOrder=OrderType(
                limitOrderExpiryDttm=context.Time + self.limitOrderExpiration,
                midPrice=orderMidPrice,
                limitOrderPrice=limitOrderPrice,
                bidAskSpread=bidAskSpread,
                maxLoss=maxLoss
            )
        )

        self.logger.debug(f"buildOrderPosition -> position: {position}")

        # Create combo orders by using the provided method instead of always calling MarketOrder.
        insights = []

        # Create the orders
        for contract in contracts:
            # Get the contract side (Long/Short)
            orderSide = contractSide[contract.Symbol]
            insight = Insight.Price(
                contract.Symbol,
                position.openOrder.limitOrderExpiryDttm,
                InsightDirection.Down if orderSide == -1 else InsightDirection.Up
            )
            insights.append(insight)

        self.logger.debug(f"buildOrderPosition -> insights: {insights}")

        # Map each contract to the openPosition dictionary (key: expiryStr)
        workingOrder = WorkingOrder(
            positionKey=orderId,
            insights=insights,
            limitOrderPrice=limitOrderPrice,
            orderId=orderId,
            strategy=self,
            strategyTag=self.nameTag,
            useLimitOrder=useLimitOrders,
            orderType="open",
            fills=0
        )

        self.logger.debug(f"buildOrderPosition -> workingOrder: {workingOrder}")

        return [position, workingOrder]

    def hasDuplicateLegs(self, order):
        # Check if checkForDuplicatePositions is enabled
        if not self.checkForDuplicatePositions:
            return False

        # Get the context
        context = self.context

        # Get the list of contracts
        contracts = order["contracts"]

        openPositions = context.openPositions

        # Iterate through open positions
        for orderTag, orderId in list(openPositions.items()):
            position = context.allPositions[orderId]

            # Check if the expiry matches
            if position.expiryStr != order["expiry"].strftime("%Y-%m-%d"):
                continue

            # Check if the strategy matches (if allowMultipleEntriesPerExpiry is False)
            if not self.allowMultipleEntriesPerExpiry and position.strategyId == order["strategyId"]:
                return True

            # Compare legs
            position_legs = set((leg.strike, leg.contractSide) for leg in position.legs)
            order_legs = set((contract.Strike, order["contractSide"][contract.Symbol]) for contract in contracts)

            if position_legs == order_legs:
                return True

        return False

    """
    This method is called every minute to update the stats dictionary.
    """
    def syncStats(self):
        # Get the current day
        currentDay = self.context.Time.date()
        # Update the underlyingPriceAtOpen to be set at the start of each day
        underlying = Underlying(self.context, self.underlyingSymbol)
        if currentDay != self.stats.currentDay:
            self.logger.trace(f"Previous day: {self.stats.currentDay} data {self.stats.underlyingPriceAtOpen}, {self.stats.highOfTheDay}, {self.stats.lowOfTheDay}")
            self.stats.underlyingPriceAtOpen = underlying.Price()
            # Update the high/low of the day
            self.stats.highOfTheDay = underlying.Close()
            self.stats.lowOfTheDay = underlying.Close()
            # Add a dictionary to keep track of whether the price has touched the EMAs
            self.stats.touchedEMAs = {}
            self.logger.debug(f"Updating stats for {currentDay} Open: {self.stats.underlyingPriceAtOpen}, High: {self.stats.highOfTheDay}, Low: {self.stats.lowOfTheDay}")
            self.stats.currentDay = currentDay
            self.stats.hasOptions = None

        # This is like poor mans consolidator
        frequency = 5 # minutes
        # Continue the processing only if we are at the specified schedule
        if self.context.Time.minute % frequency != 0:
            return None

        # This should add the data for the underlying symbol chart.
        self.context.charting.updateCharts(symbol = self.underlyingSymbol)

        # Update the high/low of the day
        self.stats.highOfTheDay = max(self.stats.highOfTheDay, underlying.Close())
        self.stats.lowOfTheDay = min(self.stats.lowOfTheDay, underlying.Close())

    # The method will be called each time a consolidator is receiving data. We have a default one of 5 minutes
    # so if we need something to happen every 5 minutes this can be used for that.
    def dataConsolidated(self, sender, consolidated):
        pass
        
    def OnSecuritiesChanged(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        # Security additions and removals are pushed here.
        # This can be used for setting up algorithm state.
        # changes.AddedSecurities
        # changes.RemovedSecurities
        pass


