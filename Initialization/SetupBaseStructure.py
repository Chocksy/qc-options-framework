#region imports
from AlgorithmImports import *
#endregion

from Tools import Timer, Logger, DataHandler, Underlying, Charting
from Initialization import AlwaysBuyingPowerModel, BetaFillModel, TastyWorksFeeModel




class SetupBaseStructure:
    """
    Manages the initialization and setup of an algorithm's base structure. This includes configuring the brokerage model,
    security initializer, option chain filter function, and scheduling market open events. The class supports chainable methods
    for easier setup and configuration.

    Attributes:
        context (QuantConnect.Algorithm.QCAlgorithm): The context in which the algorithm operates, providing access to all
            QuantConnect API methods and properties.
        DEFAULT_PARAMETERS (dict): A dictionary containing default parameters for the strategy, such as the risk-free rate
            and settings related to price models and fees.

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

    def __init__(self, context):
        self.context = context # Store the context as a class variable

    def Setup(self):
        """
        Configures various components of the algorithm such as the logger, timer, brokerage model, and security initializer.
        It sets default parameters and prepares the environment for trading. This method is typically called during the
        algorithm's Initialize method.
        """
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

        # Keep track of all strategy monitors
        self.context.strategyMonitors = {}

        # Array to keep track of consolidators
        self.context.consolidators = {}

        # Dictionary to keep track of all leg details across time
        self.positionTracking = {}

        # Keep the chain object list in memory that gets updated before every Strategy update code run.
        self.context.chain = None

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

    def CompleteSecurityInitializer(self, security: Security) -> None:
        """
        Initializes the security with raw prices. It is called every time a security (Option or Equity/Index) is initialized

        Args:
            security (Security): The security object to initialize.
        """
        self.context.logger.debug(f"{self.__class__.__name__} -> CompleteSecurityInitializer -> Security: {security}")

        # Disable buying power on the security: https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/trading-and-orders#10-Disable-Buying-Power
        security.set_buying_power_model(BuyingPowerModel.NULL)

        if self.context.LiveMode:
            return

        self.context.executionTimer.start()

        security.SetDataNormalizationMode(DataNormalizationMode.Raw)
        security.SetMarketPrice(self.context.GetLastKnownPrice(security))
        # security.SetBuyingPowerModel(AlwaysBuyingPowerModel(self.context))
        # override margin requirements
        # security.SetBuyingPowerModel(ConstantBuyingPowerModel(1))

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
        elif security.Type == SecurityType.FutureOption:
            # New handling for FutureOptions
            security.SetFillModel(BetaFillModel(self.context))
            security.SetFeeModel(TastyWorksFeeModel())
            security.PriceModel = OptionPriceModels.CrankNicolsonFD()
            security.SetOptionAssignmentModel(NullOptionAssignmentModel())

            # Initialize Greeks or any other specific models for FutureOptions
            try:
                security.iv = self.context.iv(security.symbol, security.symbol, resolution=self.context.timeResolution)
                security.delta = self.context.d(security.symbol, security.symbol, resolution=self.context.timeResolution)
                security.gamma = self.context.g(security.symbol, security.symbol, resolution=self.context.timeResolution)
                security.vega = self.context.v(security.symbol, security.symbol, resolution=self.context.timeResolution)
                security.rho = self.context.r(security.symbol, security.symbol, resolution=self.context.timeResolution)
                security.theta = self.context.t(security.symbol, security.symbol, resolution=self.context.timeResolution)
            except Exception as e:
                self.context.logger.warning(f"FutureOption Initializer: Data not available: {e}") 
        elif security.Type in [SecurityType.Option, SecurityType.IndexOption]:
            # This is for options.
            security.SetFillModel(BetaFillModel(self.context))
            # security.SetFillModel(MidPriceFillModel(self))
            security.SetFeeModel(TastyWorksFeeModel())
            security.PriceModel = OptionPriceModels.CrankNicolsonFD()
            # security.set_option_assignment_model(NullOptionAssignmentModel())

            right = OptionRight.CALL if security.symbol.ID.option_right == OptionRight.PUT else OptionRight.PUT
            mirror_symbol = Symbol.create_option(security.symbol.ID.underlying.symbol, security.symbol.ID.market, security.symbol.ID.option_style, right, security.symbol.ID.strike_price, security.symbol.ID.date)
            try:
                security.iv = self.context.iv(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.delta = self.context.d(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.gamma = self.context.g(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.vega = self.context.v(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.rho = self.context.r(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.theta = self.context.t(security.symbol, mirror_symbol, resolution=self.context.timeResolution)

            except Exception as e:
                self.context.logger.warning(f"Security Initializer: Data not available: {e}") 

        if security.Type == SecurityType.IndexOption:
            # disable option assignment. This is important for SPX but we disable for all for now.
            security.SetOptionAssignmentModel(NullOptionAssignmentModel())
        self.context.executionTimer.stop()

    def ClearSecurity(self, security: Security) -> None:
        """
        Remove any additional data or settings associated with the security.

        Args:
            security (Security): The security object to be cleared.
        """
        # Remove the security from the optionContractsSubscriptions dictionary
        if security.Symbol in self.context.optionContractsSubscriptions:
            self.context.optionContractsSubscriptions.remove(security.Symbol)

        # Remove the security from the algorithm
        self.context.RemoveSecurity(security.Symbol)

    def SetBacktestCutOffTime(self) -> None:
        """
        Determines and sets the cutoff time for the backtest based on the algorithm's end date and market close time. This
        is used to ensure that no trades occur after the specified cutoff time on the last trading day of the backtest.
        """
        self.context.endOfBacktestCutoffDttm = None
        if hasattr(self.context, "EndDate") and self.context.EndDate is not None:
            self.context.endOfBacktestCutoffDttm = datetime.combine(self.context.lastTradingDay(self.context.EndDate), self.context.backtestMarketCloseCutoffTime)

    def AddConfiguration(self, parent=None, **kwargs) -> None:
        """
        Adds configuration settings to the algorithm or a specified object within the algorithm. This method allows for
        dynamic assignment of configuration parameters.
        Args:
            parent: Parent object to which the attributes will be added.
            kwargs: Keyword arguments containing attribute names and their values.
        """
        parent = parent or self.context
        for attr_name, attr_value in kwargs.items():
            setattr(parent, attr_name, attr_value)

    def AddUnderlying(self, strategy, ticker):
        """
        Adds an underlying asset and its associated options chain to the algorithm. This is a crucial step in setting up
        an options trading strategy.

        Args:
            strategy (object): The trading strategy that requires an underlying asset.
            ticker (str): The ticker symbol of the underlying asset to be added.
        """
        self.context.strategies.append(strategy)
        # Store the algorithm base variables
        strategy.ticker = ticker
        self.context.logger.debug(f"{self.__class__.__name__} -> AddUnderlying -> Ticker: {ticker}")
        # Add the underlying and the option chain to the algorithm
        strategy.dataHandler = DataHandler(self.context, ticker, strategy)
        underlying = strategy.dataHandler.AddUnderlying(self.context.timeResolution)
        # Set data normalization mode to Raw
        underlying.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.context.logger.debug(f"{self.__class__.__name__} -> AddUnderlying -> Underlying: {underlying}")
        # Keep track of the option contract subscriptions
        self.context.optionContractsSubscriptions = []

        # Store the symbol for the option and the underlying
        strategy.underlyingSymbol = underlying.Symbol

        # REGION FOR USING SLICE INSTEAD OF PROVIDER
        strategy.optionSymbol = None
        if strategy.useSlice:
            strategy.dataHandler.SetOptionFilter(underlying)

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
        """
        Adds a consolidator to the algorithm for a specific symbol. Consolidators help in managing data resolution and
        ensuring that the algorithm processes data at the required frequency.

        Args:
            symbol (Symbol): The symbol for which the consolidator is to be added.
            minutes (int): The time interval, in minutes, for the consolidator.
        """
        consolidator = TradeBarConsolidator(timedelta(minutes=minutes))
        # Subscribe to the DataConsolidated event
        consolidator.DataConsolidated += self.onDataConsolidated
        self.context.SubscriptionManager.AddConsolidator(symbol, consolidator)
        self.context.consolidators[symbol] = consolidator

    def onDataConsolidated(self, sender, bar):
        """
        Handles data consolidation events. This method is triggered whenever new consolidated data is available and
        ensures that the algorithm processes this data appropriately.

        Args:
            sender (object): The sender of the event.
            bar (TradeBar): The consolidated data.
        """
        for strategy in self.context.strategies:
            # We don't have the underlying added yet, so we can't get the price.
            if strategy.underlyingSymbol == None:
                return

            strategy.dataConsolidated(sender, bar)

        self.context.charting.updateUnderlying(bar)

    # NOTE: this is not needed anymore as we have another method in alpha that handles it.
    def MarketOpenStructure(self):
        """
        Executes tasks that need to be performed right after the market opens. This typically includes updating the
        price of the underlying asset. This method is scheduled to run every market open day.
        """
        for strategy in self.context.strategies:
            # We don't have the underlying added yet, so we can't get the price.
            if strategy.underlyingSymbol == None:
                return

            underlying = Underlying(self.context, strategy.underlyingSymbol)
            strategy.underlyingPriceAtOpen = underlying.Price()

    def checkOpenPositions(self):
        """
        Periodically checks and manages open positions to ensure they are valid and handles any necessary cleanup or
        adjustments based on the current market conditions or the positions' expiration status.
        """
        self.context.executionTimer.start()
        # Iterate over all option contracts and remove the expired ones from the
        for symbol, security in self.context.Securities.items():
            # Check if the security is an option
            if security.Type == SecurityType.Option and security.HasData:
                # Check if the option has expired
                if security.Expiry.date() < self.context.Time.date():
                    self.context.logger.debug(f"  >>>  EXPIRED SECURITY-----> Removing expired {security.Expiry.date()} option contract {security.Symbol} from the algorithm.")
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
                self.context.logger.debug(f"  >>>  EXPIRED POSITION-----> Removing expired position {orderTag} from the algorithm.")
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
                self.context.logger.debug(f"  >>>  EXPIRED ORDER-----> Removing expired order {orderTag} from the algorithm.")
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

