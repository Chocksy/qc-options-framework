#region imports
from AlgorithmImports import *
#endregion

from Tools import Timer, Logger, DataHandler, Underlying, Charting
from Initialization import AlwaysBuyingPowerModel, BetaFillModel, TastyWorksFeeModel

"""
    This class is used to setup the base structure of the algorithm in the main.py file.
    It is used to setup the logger, the timer, the brokerage model, the security initializer, the
    option chain filter function and the benchmark.
    It is also used to schedule an event to get the underlying price at market open.
    The class has chainable methods for Setup and AddUnderlying.

    How to use it:
    1. Import the class
    2. Create an instance of the class in the Initialize method of the algorithm
    3. Call the AddUnderlying method to add the underlying and the option chain to the algorithm

    Example:

    from Initialization import SetupBaseStructure

    class Algorithm(QCAlgorithm):
        def Initialize(self):
            # Set the algorithm base variables and structures
            self.structure = SetupBaseStructure(self)
            self.structure.Setup()

            # Add the alpha model and that will add the underlying and the option chain to the
            # algorithm
            self.SetAlpha(AlphaModel(self))

    class AlphaModel:
        def __init__(self, context):
            # Store the context as a class variable
            self.context = context

            # Add the underlying and the option chain to the algorithm
            self.context.structure.AddUnderlying(self, "SPX")
"""


class SetupBaseStructure:

    # Default parameters
    DEFAULT_PARAMETERS = {
        "creditStrategy": True,
        # -----------------------------
        # THESE BELOW ARE GENERAL PARAMETERS
        "backtestMarketCloseCutoffTime": time(15, 45, 0),
        # Controls whether to include Cancelled orders (Limit orders that didn't fill) in the final output
        "includeCancelledOrders": True,
        # Risk Free Rate for the Black-Scholes-Merton model
        "riskFreeRate": 0.001,
        # Upside/Downside stress applied to the underlying to calculate the portfolio margin requirement of the position
        "portfolioMarginStress": 0.12,
        # Controls the memory (in minutes) of EMA process. The exponential decay
        # is computed such that the contribution of each value decays by 95%
        # after <emaMemory> minutes (i.e. decay^emaMemory = 0.05)
        "emaMemory": 200,
    }

    # Initialize the algorithm
    # The context is the class that contains all the variables that are shared across the different classes
    def __init__(self, context):
        # Store the context as a class variable
        self.context = context

    def Setup(self):
        self.context.positions = {}

        # Set the logger
        self.context.logger = Logger(self.context, className=type(self.context).__name__, logLevel=self.context.logLevel)

        # Set the timer to monitor the execution performance
        self.context.executionTimer = Timer(self.context)
        self.context.logger.debug(f'{self.__class__.__name__} -> Setup')
        # Set brokerage model and margin account
        self.context.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage, AccountType.Margin)
        # override security position group model
        self.context.Portfolio.SetPositions(SecurityPositionGroupModel.Null)
        # Set requested data resolution
        self.context.universe_settings.resolution = self.context.timeResolution

        # Keep track of the option contract subscriptions
        self.context.optionContractsSubscriptions = []
        # Set Security Initializer
        self.context.SetSecurityInitializer(self.CompleteSecurityInitializer)
        # Initialize the dictionary to keep track of all positions
        self.context.allPositions = {}

        # Dictionary to keep track of all open positions
        self.context.openPositions = {}

        # Create dictionary to keep track of all the working orders. It stores orderTags
        self.context.workingOrders = {}

        # Create FIFO list to keep track of all the recently closed positions (needed for the Dynamic DTE selection)
        self.context.recentlyClosedDTE = []

        # Keep track of when was the last position opened
        self.context.lastOpenedDttm = None

        # Keep track of all strategies instances. We mainly need this to filter through them in case
        # we want to call some general method.
        self.context.strategies = []

        # Array to keep track of consolidators
        self.context.consolidators = {}

        # Dictionary to keep track of all leg details across time
        self.positionTracking = {}

        # Assign the DEFAULT_PARAMETERS
        self.AddConfiguration(**SetupBaseStructure.DEFAULT_PARAMETERS)
        self.SetBacktestCutOffTime()

        # Set charting
        self.context.charting = Charting(
            self.context, 
            openPositions=False, 
            Stats=False, 
            PnL=False, 
            WinLossStats=False, 
            Performance=True, 
            LossDetails=False, 
            totalSecurities=False, 
            Trades=True
        )

        return self

    # Called every time a security (Option or Equity/Index) is initialized
    def CompleteSecurityInitializer(self, security: Security) -> None:
        '''Initialize the security with raw prices'''
        self.context.logger.debug(f"{self.__class__.__name__} -> CompleteSecurityInitializer -> Security: {security}")
        if self.context.LiveMode:
            return

        self.context.executionTimer.start()

        security.SetDataNormalizationMode(DataNormalizationMode.Raw)
        security.SetMarketPrice(self.context.GetLastKnownPrice(security))
        # security.SetBuyingPowerModel(AlwaysBuyingPowerModel(self.context))
        # override margin requirements
        security.SetBuyingPowerModel(ConstantBuyingPowerModel(1))

        if security.Type == SecurityType.Equity:
            # This is for stocks
            security.VolatilityModel = StandardDeviationOfReturnsVolatilityModel(30)
            history = self.context.History(security.Symbol, 31, Resolution.Daily)

            if history.empty or 'close' not in history.columns:
                self.context.executionTimer.stop()
                return

            for time, row in history.loc[security.Symbol].iterrows():
                trade_bar = TradeBar(time, security.Symbol, row.open, row.high, row.low, row.close, row.volume)
                security.VolatilityModel.Update(security, trade_bar)

        elif security.Type in [SecurityType.Option, SecurityType.IndexOption]:
            # This is for options.
            security.SetFillModel(BetaFillModel(self.context))
            # security.SetFillModel(MidPriceFillModel(self))
            security.SetFeeModel(TastyWorksFeeModel())
            security.PriceModel = OptionPriceModels.CrankNicolsonFD()
            # security.set_option_assignment_model(NullOptionAssignmentModel())
        if security.Type == SecurityType.IndexOption:
            # disable option assignment. This is important for SPX but we disable for all for now.
            security.SetOptionAssignmentModel(NullOptionAssignmentModel())
        self.context.executionTimer.stop()

    def ClearSecurity(self, security: Security) -> None:
        """
        Remove any additional data or settings associated with the security.
        """
        # Remove the security from the optionContractsSubscriptions dictionary
        if security.Symbol in self.context.optionContractsSubscriptions:
            self.context.optionContractsSubscriptions.remove(security.Symbol)

        # Remove the security from the algorithm
        self.context.RemoveSecurity(security.Symbol)

    def SetBacktestCutOffTime(self) -> None:
        # Determine what is the last trading day of the backtest
        self.context.endOfBacktestCutoffDttm = None
        if hasattr(self.context, "EndDate") and self.context.EndDate is not None:
            self.context.endOfBacktestCutoffDttm = datetime.combine(self.context.lastTradingDay(self.context.EndDate), self.context.backtestMarketCloseCutoffTime)

    def AddConfiguration(self, parent=None, **kwargs) -> None:
        """
        Dynamically add attributes to the self.context object.

        :param parent: Parent object to which the attributes will be added.
        :param kwargs: Keyword arguments containing attribute names and their values.
        """
        parent = parent or self.context
        for attr_name, attr_value in kwargs.items():
            setattr(parent, attr_name, attr_value)

    # Add the underlying and the option chain to the algorithm. We define the number of strikes left and right,
    # the dte and the dte window. These parameters are used in the option chain filter function.
    # @param ticker [string]
    def AddUnderlying(self, strategy, ticker):
        self.context.strategies.append(strategy)
        # Store the algorithm base variables
        strategy.ticker = ticker
        self.context.logger.debug(f"{self.__class__.__name__} -> AddUnderlying -> Ticker: {ticker}")
        # Add the underlying and the option chain to the algorithm
        strategy.dataHandler = DataHandler(self.context, ticker, strategy)
        underlying = strategy.dataHandler.AddUnderlying(self.context.timeResolution)
        option = strategy.dataHandler.AddOptionsChain(underlying, self.context.timeResolution)
        # Set data normalization mode to Raw
        underlying.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.context.logger.debug(f"{self.__class__.__name__} -> AddUnderlying -> Underlying: {underlying}")
        # Keep track of the option contract subscriptions
        self.context.optionContractsSubscriptions = []

        # Set the option chain filter function
        option.SetFilter(strategy.dataHandler.SetOptionFilter)
        self.context.logger.debug(f"{self.__class__.__name__} -> AddUnderlying -> Option: {option}")
        # Store the symbol for the option and the underlying
        strategy.underlyingSymbol = underlying.Symbol
        strategy.optionSymbol = option.Symbol

        # Set the benchmark.
        self.context.SetBenchmark(underlying.Symbol)
        self.context.logger.debug(f"{self.__class__.__name__} -> AddUnderlying -> Benchmark: {self.context.Benchmark}")
        # Creating a 5-minute consolidator.
        # self.AddConsolidators(strategy.underlyingSymbol, 5)

        # !IMPORTANT
        # !     this schedule needs to happen only once on initialization. That means the method AddUnderlying
        # !     needs to be called only once either in the main.py file or in the AlphaModel class.
        self.context.Schedule.On(
            self.context.DateRules.EveryDay(strategy.underlyingSymbol),
            self.context.TimeRules.AfterMarketOpen(strategy.underlyingSymbol, minutesAfterOpen=1),
            self.MarketOpenStructure
        )

        return self

    def AddConsolidators(self, symbol, minutes=5):
        consolidator = TradeBarConsolidator(timedelta(minutes=minutes))
        # Subscribe to the DataConsolidated event
        consolidator.DataConsolidated += self.onDataConsolidated
        self.context.SubscriptionManager.AddConsolidator(symbol, consolidator)
        self.context.consolidators[symbol] = consolidator

    def onDataConsolidated(self, sender, bar):
        for strategy in self.context.strategies:
            # We don't have the underlying added yet, so we can't get the price.
            if strategy.underlyingSymbol == None:
                return

            strategy.dataConsolidated(sender, bar)

        self.context.charting.updateUnderlying(bar)

    # NOTE: this is not needed anymore as we have another method in alpha that handles it.
    def MarketOpenStructure(self):
        """
        The MarketOpenStructure method is part of the SetupBaseStructure class, which is used to
        set up the base structure of the algorithm in the main.py file. This specific method is
        designed to be called at market open every day to update the price of the underlying
        security. It first checks if the underlying symbol has been added to the context, and if
        not, it returns without performing any action. If the underlying symbol is available, it
        creates an instance of the Underlying class using the context and the symbol. Finally,
        it updates the underlying price at the market open by calling the Price() method on the
        Underlying instance.

        Example:
        Schedule the MarketOpenStructure method to be called at market open

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.AfterMarketOpen(self.strategy.underlyingSymbol, 0), base_structure.MarketOpenStructure)

        Other methods, like OnData, can now access the updated underlying price using self.context.underlyingPriceAtOpen
        """
        for strategy in self.context.strategies:
            # We don't have the underlying added yet, so we can't get the price.
            if strategy.underlyingSymbol == None:
                return

            underlying = Underlying(self.context, strategy.underlyingSymbol)
            strategy.underlyingPriceAtOpen = underlying.Price()

    # This just clears the workingOrders that are supposed to be expired or unfilled. It can happen when an order is not filled
    # for it to stay in check until next day. This will clear that out. Similar method to the monitor one.
    def checkOpenPositions(self):
        self.context.executionTimer.start()
        # Iterate over all option contracts and remove the expired ones from the 
        for symbol, security in self.context.Securities.items():
            # Check if the security is an option
            if security.Type == SecurityType.Option:
                # Check if the option has expired
                if security.Expiry < self.context.Time:
                    self.context.logger.trace(f"  >>>  EXPIRED SECURITY-----> Removing expired option contract {security.Symbol} from the algorithm.")
                    # Remove the expired option contract
                    self.ClearSecurity(security)

        # Remove the expired positions from the openPositions dictionary. These are positions that expired
        # worthless or were closed before expiration.
        for orderTag, orderId in list(self.context.openPositions.items()):
            position = self.context.allPositions[orderId]
            # Check if we need to cancel the order
            if any(self.context.Time > leg.expiry for leg in position.legs):
                # Remove this position from the list of open positions
                self.context.charting.updateStats(position)
                self.context.logger.info(f"  >>>  EXPIRED POSITION-----> Removing expired position {position.orderTag} from the algorithm.")
                self.context.openPositions.pop(orderTag)

        # Remove the expired positions from the workingOrders dictionary. These are positions that expired
        # without being filled completely.
        for order in list(self.context.workingOrders.values()):
            position = self.context.allPositions[order.orderId]
            orderTag = position.orderTag
            orderId = position.orderId
            orderType = order.orderType
            execOrder = position[f"{orderType}Order"]

            # Check if we need to cancel the order
            if self.context.Time > execOrder.limitOrderExpiryDttm or any(self.context.Time > leg.expiry for leg in position.legs):
                # Remove this position from the list of open positions
                if orderTag in self.context.openPositions:
                    self.context.openPositions.pop(orderTag)
                # Remove the cancelled position from the final output unless we are required to include it
                if not self.context.includeCancelledOrders:
                    self.context.allPositions.pop(orderId)
                # Remove the order from the self.context.workingOrders dictionary
                if orderTag in self.context.workingOrders:
                    self.context.workingOrders.pop(orderTag)
                # Mark the order as being cancelled
                position.cancelOrder(self.context, orderType=orderType, message=f"order execution expiration or legs expired")
        self.context.executionTimer.stop()
