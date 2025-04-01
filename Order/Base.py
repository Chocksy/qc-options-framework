# region imports
from AlgorithmImports import *
# endregion
from Order import Order
from Tools import ContractUtils, Logger, Underlying
from Strategy import Leg, Position, OrderType, WorkingOrder

class Base:
    # Internal counter for all the orders
    orderCount = 0

    def __init__(self, context, strategy):
        self.context = context
        # Set the logger
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)
        self.strategy = strategy
        # Set default name (use the class name)
        self.name = strategy.name
        # Set the Strategy Name (optional)
        self.nameTag = strategy.nameTag
        # Initialize the contract utils
        self.contractUtils = ContractUtils(context)

    def updateChain(self, chain):
        self.context.chain = chain

    def buildOrderPosition(self, order, lastClosedOrderTag=None):
        # Get the context
        context = self.context

        # Get the list of contracts
        contracts = order["contracts"]
        self.logger.debug(f"buildOrderPosition -> contracts: {len(contracts)}")
        # Exit if there are no contracts
        if (len(contracts) == 0):
            return [None, None]

        # Check position limits first
        if not self.check_position_limits(order):
            return [None, None]

        useLimitOrders = self.strategy.useLimitOrders
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
                or (self.strategy.validateQuantity and orderQuantity > maxOrderQuantity)
                # Make sure the bid-ask spread is not too wide before opening the position.
                # Only for Market orders. In case of limit orders, this validation is done at the time of execution of the Limit order
                or (useMarketOrders and self.strategy.validateBidAskSpread
                    and abs(bidAskSpread) >
                    self.strategy.bidAskSpreadRatio * abs(orderMidPrice))):
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
                limitOrderExpiryDttm=context.Time + self.strategy.limitOrderExpiration,
                midPrice=orderMidPrice,
                limitOrderPrice=limitOrderPrice,
                bidAskSpread=bidAskSpread,
                maxLoss=maxLoss
            )
        )

        self.logger.debug(f"buildOrderPosition -> position: {position.summarize()}")

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

        self.logger.debug(f"buildOrderPosition -> workingOrder: {workingOrder.summarize()}")

        return [position, workingOrder]

    @staticmethod
    def getNextOrderId():
        try:
            max_order_id = max(orderId for _, orderId in self.context.openPositions.items())
        except:
            max_order_id = 0

        if max_order_id > 0 and Base.orderCount == 0:
            Base.orderCount = max_order_id + 1
        else:
            Base.orderCount += 1
            
        return Base.orderCount

    def hasReachedMaxActivePositions(self) -> bool:
        """Check if maximum number of active positions has been reached."""
        openPositionsByStrategy = {
            tag: pos for tag, pos in self.context.openPositions.items() 
            if self.context.allPositions[pos].strategyTag == self.nameTag
        }
        workingOrdersByStrategy = {
            tag: order for tag, order in self.context.workingOrders.items() 
            if order.strategyTag == self.nameTag
        }
        
        return (len(openPositionsByStrategy) + len(workingOrdersByStrategy)) >= self.maxActivePositions

    def hasReachedMaxOpenPositions(self) -> bool:
        """Check if maximum number of open orders has been reached."""
        workingOrdersByStrategy = {
            tag: order for tag, order in self.context.workingOrders.items() 
            if order.strategyTag == self.nameTag
        }
        
        return len(workingOrdersByStrategy) >= self.maxOpenPositions

    def check_position_limits(self, order) -> bool:
        """
        Checks if placing this order would violate position limits.
        Returns True if order is within limits, False otherwise.
        """
        # Check max active positions
        max_active = self.strategy.parameter("maxActivePositions", 1)
        active_positions = len([p for p in self.context.Portfolio.Values if p.Invested])
        if active_positions >= max_active:
            return False
            
        # Check max open orders
        max_open = self.strategy.parameter("maxOpenPositions", 2)
        open_orders = len([o for o in self.context.Transactions.GetOpenOrders()])
        if open_orders >= max_open:
            return False
            
        # Check for duplicate positions if configured
        if self.strategy.parameter("checkForDuplicatePositions", True):
            if self.hasDuplicateLegs(order):
                return False
                
        return True

    def hasDuplicateLegs(self, order) -> bool:
        """
        Check if any legs in the order are already part of an existing position.
        """
        # Get all open positions
        open_positions = [self.context.allPositions[tag] for tag in self.context.openPositions.values()]
        
        # Get the expiry date from the order
        order_expiry = order["expiry"].strftime("%Y-%m-%d")
        
        # Check each open position
        for position in open_positions:
            # Skip positions from other strategies
            if position.strategyId != order["strategyId"]:
                continue
                
            # Skip positions with different expiry dates if allowed
            if self.strategy.parameter("allowMultipleEntriesPerExpiry", False):
                if position.expiryStr != order_expiry:
                    continue
                    
            # Check if any legs match
            for leg in position.legs:
                for contract in order["contracts"]:
                    if (leg.strike == contract.Strike and 
                        leg.contractSide == order["contractSide"][contract.Symbol]):
                        return True
                        
        return False