from AlgorithmImports import *

from Tools import ContractUtils, Logger
from Execution.Utils import MarketOrderHandler, LimitOrderHandler, LimitOrderHandlerWithCombo
"""
"""

class Base(ExecutionModel):
    DEFAULT_PARAMETERS = {
        # Retry decrease/increase percentage. Each time we try and get a fill we are going to decrease the limit price
        # by this percentage.
        "retryChangePct": 1.0,
        # Minimum price percentage accepted as limit price. If the limit price set is 0.5 and this value is 0.8 then
        # the minimum price accepted will be 0.4
        "minPricePct": 0.7,
        # The limit order price initial adjustmnet. This will add some leeway to the limit order price so we can try and get
        # some more favorable price for the user than the algo set price. So if we set this to 0.1 (10%) and our limit price
        # is 0.5 then we will try and fill the order at 0.55 first.
        "orderAdjustmentPct": -0.2,
        # The increment we are going to use to adjust the limit price. This is used to 
        # properly adjust the price for SPX options. If the limit price is 0.5 and this
        # value is 0.01 then we are going to try and fill the order at 0.51, 0.52, 0.53, etc.
        "adjustmentIncrement": None, # 0.01,
        # Speed of fill. Option taken from https://optionalpha.com/blog/smartpricing-released. 
        # Can be: "Normal", "Fast", "Patient"
        # "Normal" will retry every 3 minutes, "Fast" every 1 minute, "Patient" every 5 minutes.
        "speedOfFill": "Fast",
        # maxRetries is the maximum number of retries we are going to do to try 
        # and get a fill. This is calculated based on the speedOfFill and this 
        # value is just for reference.
        "maxRetries": 10,
    }

    def __init__(self, context):
        self.context = context
        self.targetsCollection = PortfolioTargetCollection()
        self.contractUtils = ContractUtils(context)
        # Set the logger
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)
        self.marketOrderHandler = MarketOrderHandler(context, self)
        # self.limitOrderHandler = LimitOrderHandler(context, self)
        self.limitOrderHandler = LimitOrderHandlerWithCombo(context, self)
        self.logger.debug(f"{self.__class__.__name__} -> __init__")
        # Gets or sets the maximum spread compare to current price in percentage.
        # self.acceptingSpreadPercent = Math.Abs(acceptingSpreadPercent)
        # self.executionTimeThreshold = timedelta(minutes=10)
        # self.openExecutedOrders = {}

        self.context.structure.AddConfiguration(parent=self, **self.getMergedParameters())

    @classmethod
    def getMergedParameters(cls):
        # Merge the DEFAULT_PARAMETERS from both classes
        return {**cls.DEFAULT_PARAMETERS, **getattr(cls, "PARAMETERS", {})}

    @classmethod
    def parameter(cls, key, default=None):
        return cls.getMergedParameters().get(key, default)

    def Execute(self, algorithm, targets):
        self.context.executionTimer.start('Execution.Base -> Execute')

        # Add condition to return based on speedOfFill
        speed_of_fill = self.parameter("speedOfFill")
        current_minute = algorithm.Time.minute

        if speed_of_fill == "Patient" and current_minute % 5 != 0:
            return
        elif speed_of_fill == "Normal" and current_minute % 3 != 0:
            return
        # For "Fast", we execute every minute, so no condition needed

        # Use this section to check if a target is in the workingOrder dict
        self.targetsCollection.AddRange(targets)
        self.logger.debug(f"{self.__class__.__name__} -> Execute -> targets: {targets}")
        self.logger.debug(f"{self.__class__.__name__} -> Execute -> targets count: {len(targets)}")
        self.logger.debug(f"{self.__class__.__name__} -> Execute -> workingOrders: {self.logger.summarize_dict(self.context.workingOrders)}")
        
        # Replace the verbose allPositions log with a summarized version
        self.logger.debug(f"{self.__class__.__name__} -> Execute -> allPositions: {self.logger.summarize_dict(self.context.allPositions)}")
        
        # Check if the workingOrders are still OK to execute
        self.context.structure.checkOpenPositions()
        self.logger.debug(f"{self.__class__.__name__} -> Execute -> checkOpenPositions")
        max_retries = self.parameter("maxRetries")
        for order in list(self.context.workingOrders.values()):
            if order.fillRetries > max_retries:
                self.logger.debug(f"Order {order.orderId} exceeded max retries. Skipping.")
                continue

            position = self.context.allPositions[order.orderId]

            useLimitOrders = order.useLimitOrder
            useMarketOrders = not useLimitOrders
            self.logger.debug(f"Processing order: {order.orderId}")
            self.logger.debug(f"Order details: {order.summarize()}")
            self.logger.debug(f"Position details: {position.summarize()}")
            self.logger.debug(f"Use Limit Orders: {useLimitOrders}")
            self.logger.debug(f"Use Market Orders: {useMarketOrders}")
            if useMarketOrders:
                self.marketOrderHandler.call(position, order)
            elif useLimitOrders:
                self.limitOrderHandler.call(position, order)

        # if not self.targetsCollection.IsEmpty:
        #     for target in targets:
        #         order = Helper().findIn(
        #             self.context.workingOrders.values(),
        #             lambda v: any(t == target for t in v.targets)
        #         )
        #         orders[order.orderId] = order

        #     for order in orders.values():
        #         position = self.context.allPositions[order.orderId]
        #         useLimitOrders = order.useLimitOrder
        #         useMarketOrders = not useLimitOrders

        #         if useMarketOrders:
        #             self.executeMarketOrder(position, order)
        #         elif useLimitOrders:
        #             self.executeLimitOrder(position, order)

        self.targetsCollection.ClearFulfilled(algorithm)
        # Update the charts after execution
        self.context.charting.updateCharts()

        self.context.executionTimer.stop('Execution.Base -> Execute')