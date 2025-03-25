#region imports
from AlgorithmImports import *
#endregion

import dataclasses
from dataclasses import dataclass, field
from operator import attrgetter
from typing import Dict, List, Optional
from Tools import ContractUtils
import importlib
from Tools import Helper, ContractUtils, Logger, Underlying


"""
Use it like this:

position_key = "some_key"  # Replace with an appropriate key
position_data = Position(
                    orderId="12345", 
                    orderTag="SPX_Put", 
                    Strategy="CreditPutSpread", 
                    StrategyTag="CPS", 
                    expiryStr="20220107", 
                    openDttm="2022-01-07 09:30:00", 
                    openDt="2022-01-07", 
                    openDTE=0, 
                    targetPremium=500, 
                    orderQuantity=1, 
                    maxOrderQuantity=5, 
                    openOrderMidPrice=10.0,
                    openOrderMidPriceMin=9.0, 
                    openOrderMidPriceMax=11.0, 
                    openOrderBidAskSpread=1.0, 
                    openOrderLimitPrice=10.0, 
                    underlyingPriceAtOpen=4500.0
                    )

# Create Leg objects for sold and bought options
sold_put_leg = Leg(leg_type="SoldPut", option_symbol="SPXW220107P4500", quantity=-1, strike=4500, expiry="20220107")
bought_put_leg = Leg(leg_type="BoughtPut", option_symbol="SPXW220107P4490", quantity=1, strike=4490, expiry="20220107")

# Add the Leg objects to the Position's legs attribute
position_data.legs.extend([sold_put_leg, bought_put_leg])

# Add the Position to the self.positions dictionary
self.positions[position_key] = position_data
"""

@dataclass
class _ParentBase:
    """
    Acts as a utility base class for dataclass instances, enabling attribute access via both dot notation and dictionary-like key access.
    It also provides a custom representation that omits fields with default values to simplify debugging and logging outputs.
    """
    # With the __getitem__ and __setitem__ methods here we are transforming the
    # dataclass into a regular dict. This method is to allow getting fields using ["field"]
    def __getitem__(self, key):
        return super().__getattribute__(key)

    def __setitem__(self, key, value):
        return super().__setattr__(key, value)

    r"""Skip default fields in :func:`~dataclasses.dataclass`
    :func:`object representation <repr()>`.
    Notes
    -----
    Credit: Pietro Oldrati, 2022-05-08, Unilicense
    https://stackoverflow.com/a/72161437/1396928
    """
    def	__repr__(self):
        """Omit default fields in object representation."""
        nodef_f_vals = (
            (f.name, attrgetter(f.name)(self))
            for f in dataclasses.fields(self)
            if attrgetter(f.name)(self) != f.default
        )

        nodef_f_repr = ", ".join(f"{name}={value}" for name, value in nodef_f_vals)
        return f"{self.__class__.__name__}({nodef_f_repr})"

    def asdict(self):
        """
        Recursive method that checks the fields of each dataclass and calls asdict if we have another dataclass referenced
        otherwise it just builds a dictionary and assigns the values and keys.
        """
        result = {}
        for f in dataclasses.fields(self):
            fieldValue = attrgetter(f.name)(self)
            if isinstance(fieldValue, dict):
                result[f.name] = {}
                for k, v in fieldValue.items():
                    if hasattr(type(v), "__dataclass_fields__"):
                        result[f.name][k] = v.asdict()
                    else:
                        result[f.name][k] = v
            elif hasattr(type(fieldValue), "__dataclass_fields__"):
                result[f.name] = fieldValue.asdict()
            else:
                if fieldValue != f.default: result[f.name] = fieldValue
        return result


@dataclass
class WorkingOrder(_ParentBase):
    """
    Represents an order in the trading system, tracking its execution state, associated strategy, and other metadata necessary for managing trading actions.

    Attributes:
        positionKey (str): A unique key identifying the position associated with this order.
        insights (List[Insight]): Insights generated that led to this order.
        targets (List[PortfolioTarget]): Targets detailing the desired state of the portfolio following this order.
        orderId (str): Unique identifier for the order.
        strategy (str): Name of the strategy implementation governing this order.
        strategyTag (str): Tag associated with the strategy for identification.
        orderType (str): Type of order, e.g., 'limit', 'market'.
        fills (int): Number of fills that have occurred for this order.
        useLimitOrder (bool): Whether a limit order is used.
        limitOrderPrice (float): The price at which the limit order is set.
        lastRetry (Optional[datetime.date]): Date of the last retry attempt for this order.
        fillRetries (int): Number of retry attempts to fill this order.
    """
    positionKey: str = ""
    insights: List[Insight] = field(default_factory=list)
    targets: List[PortfolioTarget] = field(default_factory=list)
    orderId: str = ""
    strategy: str = "" # Ex: FPLModel actual class
    strategyTag: str = "" # Ex: FPLModel
    orderType: str = ""
    fills: int = 0
    useLimitOrder: bool = True
    limitOrderPrice: float = 0.0
    lastRetry: Optional[datetime.date] = None
    fillRetries: int = 0 # number retries to get a fill
    
    def summarize(self):
        """
        Returns a concise representation of the working order with only essential fields.
        This is useful for logging purposes to avoid very verbose output.
        
        Returns:
            dict: A dictionary with essential working order information
        """
        # Create summary dict with essential fields
        summary = {
            "positionKey": self.positionKey,
            "orderId": self.orderId,
            "strategyTag": self.strategyTag,
            "orderType": self.orderType,
            "fills": self.fills,
            "fillRetries": self.fillRetries,
            "useLimitOrder": self.useLimitOrder,
            "limitOrderPrice": self.limitOrderPrice
        }
        
        # Add lastRetry if present, formatted as a string
        if self.lastRetry is not None:
            summary["lastRetry"] = str(self.lastRetry)
            
        # Add insight and target counts instead of full objects
        if self.insights:
            summary["insightsCount"] = len(self.insights)
            
        if self.targets:
            summary["targetsCount"] = len(self.targets)
            
        return summary

@dataclass
class Leg(_ParentBase):
    """
    Represents a single leg of a trading position, detailing the specific contract and its characteristics used in the position.

    Attributes:
        key (str): A unique identifier for the leg within its position.
        expiry (Optional[datetime.date]): Expiration date of the option contract.
        contractSide (int): Side of the contract, indicating whether it is a buy or sell.
        symbol (str): Symbol of the contract.
        quantity (int): Number of contracts in the leg.
        strike (float): Strike price of the option.
        contract (OptionContract): The actual option contract object.
    """
    key: str = ""
    expiry: Optional[datetime.date] = None
    contractSide: int = 0  # TODO: this one i think would be the one to use instead of self.contractSide
    symbol: str = ""
    quantity: int = 0
    strike: float = 0.0
    contract: OptionContract = None

    # attributes used for order placement
    # orderSide: int  # TODO: also this i'm not sure what it brings as i can use contractSide.
    # orderQuantity: int
    # limitPrice: float

    @property
    def isCall(self):
        return self.contract.Right == OptionRight.Call
    
    @property
    def isPut(self):
        return self.contract.Right == OptionRight.Put
    
    @property
    def isSold(self):
        return self.contractSide == -1
    
    @property
    def isBought(self):
        return self.contractSide == 1


@dataclass
class OrderType(_ParentBase):
    """
    Encapsulates details about a specific type of order within a trading position, such as a limit order used for opening or closing positions.

    Attributes:
        premium (float): Premium of the order.
        fills (int): Number of times the order has been filled.
        limitOrderExpiryDttm (str): Expiry date and time of the limit order.
        limitOrderPrice (float): Price at which the limit order is set.
        bidAskSpread (float): Bid-ask spread at the time of the order.
        midPrice (float): Mid price at the time of the order.
        midPriceMin (float): Minimum mid price recorded for the order.
        midPriceMax (float): Maximum mid price recorded for the order.
        limitPrice (float): Limit price for the order if different from limitOrderPrice.
        fillPrice (float): Price at which the order was filled.
        openPremium (float): Premium of the order when opened.
        stalePrice (bool): Indicates if the current price is considered stale.
        filled (bool): Whether the order has been completely filled.
        maxLoss (float): Maximum loss expected from the order.
        transactionIds (List[int]): List of transaction IDs associated with the order.
        priceProgressList (List[float]): List of prices documenting the price progression of the order.
    """
    premium: float = 0.0
    fills: int = 0
    limitOrderExpiryDttm: str = ""
    limitOrderPrice: float = 0.0
    bidAskSpread: float = 0.0
    midPrice: float = 0.0
    midPriceMin: float = 0.0
    midPriceMax: float = 0.0
    limitPrice: float = 0.0
    fillPrice: float = 0.0
    openPremium: float = 0.0
    stalePrice: bool = False
    filled: bool = False
    maxLoss: float = 0.0
    transactionIds: List[int] = field(default_factory=list)
    priceProgressList: List[float] = field(default_factory=list)

@dataclass
class Position(_ParentBase):
    """
    Represents a trading position, detailing its strategy, associated orders, and lifecycle metrics.

    Attributes:
        orderId (str): Identifier for the position's order.
        orderTag (str): Tag associated with the order for easy identification.
        strategy (str): Strategy class name associated with the position.
        strategyTag (str): Tag for the strategy used.
        strategyId (str): Identifier for the strategy type, e.g., 'PutCreditSpread'.
        expiryStr (str): String representation of the expiry date.
        expiry (Optional[datetime.date]): Actual expiry date of the position.
        linkedOrderTag (str): Tag linked to other related orders or positions.
        targetPremium (float): Target premium aimed for the position.
        orderQuantity (int): Quantity of orders placed for the position.
        maxOrderQuantity (int): Maximum allowable order quantity for this position.
        targetProfit (Optional[float]): Target profit for the position.
        legs (List[Leg]): List of 'Leg' instances representing each leg of the position.
        contractSide (Dict[str, int]): Mapping of contract symbols to their sides (buy/sell).

        # Lifecycle attributes
        openOrder (OrderType): Order details at the position opening.
        closeOrder (OrderType): Order details at the position closing.
        openDttm (str): DateTime at which the position was opened.
        openDt (str): Date at which the position was opened.
        openDTE (int): Days to expiry at the time of position opening.
        openOrderMidPrice (float): Mid price of the order at opening.
        openOrderMidPriceMin (float): Minimum recorded mid price at opening.
        openOrderMidPriceMax (float): Maximum recorded mid price at opening.
        openOrderBidAskSpread (float): Bid-ask spread at the time of position opening.
        openOrderLimitPrice (float): Limit price of the order at opening.
        openPremium (float): Premium of the order at opening.
        underlyingPriceAtOpen (float): Price of the underlying asset at the time of opening.
        ... additional attributes documenting changes and status through the position's lifecycle.
    """
    # These are structural attributes that never change.
    orderId: str = "" # Ex: 1
    orderTag: str = "" # Ex: PutCreditSpread-1
    strategy: str = "" # Ex: FPLModel actual class
    strategyTag: str = "" # Ex: FPLModel
    strategyId: str = "" # Ex: PutCreditSpread, IronCondor
    expiryStr: str = ""
    expiry: Optional[datetime.date] = None
    linkedOrderTag: str = ""
    targetPremium: float = 0.0
    orderQuantity: int = 0
    maxOrderQuantity: int = 0
    targetProfit: Optional[float] = None
    legs: List[Leg] = field(default_factory=list)
    contractSide: Dict[str, int] = field(default_factory=dict)

    # These are attributes that change based on the position's lifecycle.
    # The first set of attributes are set when the position is opened.
    # Attributes that hold data about the order type
    openOrder: OrderType = field(default_factory=OrderType)
    closeOrder: OrderType = field(default_factory=OrderType)

    # Open attributes that will be set when the position is opened.
    openDttm: str = ""
    openDt: str = ""
    openDTE: int = 0
    openOrderMidPrice: float = 0.0
    openOrderMidPriceMin: float = 0.0
    openOrderMidPriceMax: float = 0.0
    openOrderBidAskSpread: float = 0.0
    openOrderLimitPrice: float = 0.0
    openPremium: float = 0.0
    underlyingPriceAtOpen: float = 0.0

    openFilledDttm: float = 0.0
    openStalePrice: bool = False

    # Attributes that hold the current state of the position
    orderMidPrice: float = 0.0
    limitOrderPrice: float = 0.0
    bidAskSpread: float = 0.0
    positionPnL: float = 0.0

    # Close attributes that will be set when the position is closed.
    closeDttm: str = ""
    closeDt: str = ""
    closeDTE: float = float("NaN")
    closeOrderMidPrice: float = 0.0
    closeOrderMidPriceMin: float = 0.0
    closeOrderMidPriceMax: float = 0.0
    closeOrderBidAskSpread: float = float("NaN")
    closeOrderLimitPrice: float = 0.0
    closePremium: float = 0.0
    underlyingPriceAtClose: float = float("NaN")
    underlyingPriceAtOrderClose: float = float("NaN")
    DIT: int = 0  # days in trade

    closeStalePrice: bool = False
    closeReason: List[str] = field(default_factory=list, init=False)

    # Other attributes that will hold the P&L and other stats.
    PnL: float = 0.0
    PnLMin: float = 0.0
    PnLMax: float = 0.0
    PnLMinDIT: float = 0.0
    PnLMaxDIT: float = 0.0

    # Attributes that determine the status of the position.
    orderCancelled: bool = False
    filled: bool = False
    limitOrder: bool = False  # True if we want the order to be a limit order when it is placed.
    priceProgressList: List[float] = field(default_factory=list)

    def underlyingSymbol(self):
        if not self.legs:
            raise ValueError(f"Missing legs/contracts")
        contracts = [v.symbol for v in self.legs]
        return contracts[0].Underlying

    def strategyModule(self):
        try:
            strategy_module = importlib.import_module(f'Alpha.{self.strategy.name}')
            strategy_class = getattr(strategy_module, self.strategy.name)
            return strategy_class
        except (ImportError, AttributeError):
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def strategyParam(self, parameter_name):
        """
        Creates a Position instance.

        Example:
            pos = Position(
                orderId="123",
                orderTag="ABC",
                strategy="TestAlphaModel",
                strategyTag="XYZ",
                expiryStr="2023-12-31"
            )

        Get targetProfit parameter from the position's strategy
            print(pos.strategyParam('targetProfit'))  // 0.5
        """
        return self.strategyModule().parameter(parameter_name)

    @property
    def isCreditStrategy(self):
        return self.strategyId in ["PutCreditSpread", "CallCreditSpread", "IronCondor", "IronFly", "CreditButterfly", "ShortStrangle", "ShortStraddle", "ShortCall", "ShortPut"]
    
    @property
    def isDebitStrategy(self):
        return self.strategyId in ["DebitButterfly", "ReverseIronFly", "ReverseIronCondor", "CallDebitSpread", "PutDebitSpread", "LongStrangle", "LongStraddle", "LongCall", "LongPut"]

    # Slippage used to set Limit orders
    def getPositionValue(self, context):
        """
        Calculates and updates the position's value based on the current market conditions and the defined slippage for each leg in the position. It also validates the bid-ask spread to ensure it's not excessively wide.
        This method also updates several attributes related to the position's market value, including the order mid-price, limit order price, bid-ask spread, and position P&L.

        Args:
            context: The trading context which provides necessary utilities and parameters.
        """
        # Start the timer
        context.executionTimer.start()
        contractUtils = ContractUtils(context)

        # Get the amount of credit received to open the position
        openPremium = self.openOrder.premium
        orderQuantity = self.orderQuantity
        slippage = self.strategyParam("slippage")

        # Loop through all legs of the open position
        orderMidPrice = 0.0
        limitOrderPrice = 0.0
        bidAskSpread = 0.0
        for leg in self.legs:
            contract = leg.contract
            # Reverse the original contract side
            orderSide = -self.contractSide[leg.symbol]
            # Compute the Bid-Ask spread
            bidAskSpread += contractUtils.bidAskSpread(contract)
            # Get the latest mid-price
            midPrice = contractUtils.midPrice(contract)
            # Adjusted mid-price (including slippage)
            adjustedMidPrice = midPrice + orderSide * slippage
            # Total order mid-price
            orderMidPrice -= orderSide * midPrice
            # Total Limit order mid-price (including slippage)
            limitOrderPrice -= orderSide * adjustedMidPrice

            # Add the parameters needed to place a Market/Limit order if needed
            leg.orderSide = orderSide
            leg.orderQuantity = orderQuantity
            leg.limitPrice = adjustedMidPrice

        # Check if the mid-price is positive: avoid closing the position if the Bid-Ask spread is too wide (more than 25% of the credit received)
        positionPnL = openPremium + orderMidPrice * orderQuantity
        if self.strategyParam("validateBidAskSpread") and bidAskSpread > self.strategyParam("bidAskSpreadRatio") * openPremium:
            context.logger.trace(f"The Bid-Ask spread is too wide. Open Premium: {openPremium},  Mid-Price: {orderMidPrice},  Bid-Ask Spread: {bidAskSpread}")
            positionPnL = None

        # Store the full mid-price of the position
        self.orderMidPrice = orderMidPrice
        # Store the Limit Order mid-price of the position (including slippage)
        self.limitOrderPrice = limitOrderPrice
        # Store the full bid-ask spread of the position
        self.bidAskSpread = bidAskSpread
        # Store the position PnL
        self.positionPnL = positionPnL

        # Stop the timer
        context.executionTimer.stop()

    def updateStats(self, context, orderType):
        """
        Updates statistics for the position based on the current market data. This includes updating the price of the underlying at the time of submitting the order.

        Args:
            context: The trading context which provides access to market data.
            orderType (str): The type of the order ('open' or 'close') which indicates at which stage the stats are being updated.
        """
        underlying = Underlying(context, self.underlyingSymbol())
        # If we do use combo orders then we might not need to do this check as it has the midPrice in there.
        # Store the price of the underlying at the time of submitting the Market Order
        self[f"underlyingPriceAt{orderType.title()}"] = underlying.Close()

    def updateOrderStats(self, context, orderType):
        """
        Updates various statistical and financial metrics for the order based on its type and the current market data. 
        
        Args:
            context: The trading context providing market data and utilities.
            orderType (str): Indicates whether the stats are for opening or closing the order.

        """
        # Start the timer
        context.executionTimer.start()

        # leg = next((leg for leg in self.legs if contract.Symbol == leg.symbol), None)
        # Get the side of the contract at the time of opening: -1 -> Short   +1 -> Long
        # contractSide = leg.contractSide
        contractUtils = ContractUtils(context)

        # Get the contracts
        contracts = [v.contract for v in self.legs]

        # Get the slippage
        slippage = self.strategyParam("slippage") or 0.0

        # Sign of the order: open -> 1 (use orderSide as is),  close -> -1 (reverse the orderSide)
        orderSign = 2*int(orderType == "open")-1
        # Sign of the transaction: open -> -1,  close -> +1
        transactionSign = -orderSign
        # Get the mid price of each contract
        prices = np.array(list(map(contractUtils.midPrice, contracts)))
        # Get the order sides
        orderSides = np.array([c.contractSide for c in self.legs])
        # Total slippage
        totalSlippage = sum(abs(orderSides)) * slippage
        # Compute the total order price (including slippage)
        # This calculates the sum of contracts midPrice so the midPrice difference between contracts.
        midPrice = transactionSign * sum(orderSides * prices) - totalSlippage
        # Compute Bid-Ask spread
        bidAskSpread = sum(list(map(contractUtils.bidAskSpread, contracts)))

        # Store the Open/Close Fill Price (if specified)
        closeFillPrice = self.closeOrder.fillPrice
        order = self[f"{orderType}Order"]
        # Keep track of the Limit order mid-price range
        order.midPriceMin = min(order.midPriceMin, midPrice)
        order.midPriceMax = max(order.midPriceMax, midPrice)
        order.midPrice = midPrice
        order.bidAskSpread = bidAskSpread

        # Exit if we don't need to include the details
        # if not self.strategyParam("includeLegDetails") or context.Time.minute % self.strategyParam("legDatailsUpdateFrequency") != 0:
        #     return

        # # Get the EMA memory factor
        # emaMemory = self.strategyParam("emaMemory")
        # # Compute the decay such that the contribution of each new value drops to 5% after emaMemory iterations
        # emaDecay = 0.05**(1.0/emaMemory)

        # # Update the counter (used for the average)
        # bookPosition["statsUpdateCount"] += 1
        # statsUpdateCount = bookPosition["statsUpdateCount"]

        # # Compute the Greeks (retrieve it as a dictionary)
        # greeks = self.bsm.computeGreeks(contract).__dict__
        # # Add the midPrice and PnL values to the greeks dictionary to generalize the processing loop
        # greeks["midPrice"] = midPrice

        # # List of variables for which we are going to update the stats
        # #vars = ["midPrice", "Delta", "Gamma", "Vega", "Theta", "Rho", "Vomma", "Elasticity", "IV"]
        # vars = [var.title() for var in self.strategyParam("greeksIncluded")] + ["midPrice", "IV"]

        # Get the fill price at the open
        openFillPrice = self.openOrder.fillPrice
        # Check if the fill price is set
        if not math.isnan(openFillPrice):
            # Compute the PnL of position. openPremium will be positive for credit and closePremium will be negative so we just add them together.
            self.PnL = self.openPremium + self.closePremium

            # Add the PnL to the list of variables for which we want to update the stats
            # vars.append("PnL")
            # greeks["PnL"] = PnL

        # for var in vars:
        #     # Set the name of the field to be updated
        #     fieldName = f"{fieldPrefix}.{var}"
        #     strategyLeg = positionStrategyLeg[var]
        #     # Get the latest value from the dictionary
        #     fieldValue = greeks[var]
        #     # Special case for the PnL
        #     if var == "PnL" and statsUpdateCount == 2:
        #         # Initialize the EMA for the PnL
        #         strategyLeg.EMA = fieldValue
        #     # Update the Min field
        #     strategyLeg.Min = min(strategyLeg.Min, fieldValue)
        #     # Update the Max field
        #     strategyLeg.Max = max(strategyLeg.Max, fieldValue)
        #     # Update the Close field (this is the most recent value of the greek)
        #     strategyLeg.Close = fieldValue
        #     # Update the EMA field (IMPORTANT: this must be done before we update the Avg field!)
        #     strategyLeg.EMA = emaDecay * strategyLeg.EMA + (1-emaDecay)*fieldValue
        #     # Update the Avg field
        #     strategyLeg.Avg = (strategyLeg.Avg*(statsUpdateCount-1) + fieldValue)/statsUpdateCount
        #     if self.strategyParam("trackLegDetails") and var == "IV":
        #         if context.Time not in context.positionTracking[self.orderId]:
        #             context.positionTracking[self.orderId][context.Time] = {"orderId": self.orderId
        #                                                                 , "Time": context.Time
        #                                                                 }
        #             context.positionTracking[self.orderId][context.Time][fieldName] = fieldValue

        # Stop the timer
        context.executionTimer.stop()

    def updatePnLRange(self, currentDate, positionPnL):
        """
        Updates the profit and loss (P&L) range for the position based on its performance on the given date. This includes recording the highest and lowest P&L and the days in trade when these occurred.

        Args:
            currentDate (datetime): The current date for which the P&L is being updated.
            positionPnL (float): The P&L of the position on the current date.        
        """
        # How many days has this position been in trade for
        # currentDit = (self.context.Time.date() - bookPosition.openFilledDttm.date()).days
        currentDit = (currentDate - self.openFilledDttm.date()).days
        # Keep track of the P&L range throughout the life of the position (mark the DIT of when the Min/Max PnL occurs)
        if 100 * positionPnL < self.PnLMax:
            self.PnLMinDIT = currentDit
            self.PnLMin = min(self.PnLMin, 100 * positionPnL)
        if 100 * positionPnL > self.PnLMax:
            self.PnLMaxDIT = currentDit
            self.PnLMax = max(self.PnLMax, 100 * positionPnL)

    def expiryLastTradingDay(self, context):
        """
        Determines the last trading day before the position's expiry date, considering holidays and other non-trading days.

        Args:
            context: The trading context which includes calendar and scheduling utilities.

        Returns:
            datetime: The last possible trading day before the position's expiry.
        """
        return context.lastTradingDay(self.expiry)

    def expiryMarketCloseCutoffDttm(self, context):
        """
        Calculates the exact datetime by which a position must be closed on its last trading day to adhere to market or strategy-specific rules.

        Args:
            context: The trading context which includes timing and scheduling utilities.

        Returns:
            datetime: The cutoff datetime on the last trading day before the position's expiry.
        """
        return datetime.combine(self.expiryLastTradingDay(context), self.strategyParam("marketCloseCutoffTime"))

    def cancelOrder(self, context, orderType = 'open', message = ''):
        """
        Cancels an order associated with this position, typically due to expiration or failure to fill within the expected timeframe. It logs the cancellation and updates relevant statistics.

        Args:
            context: The trading context which provides access to transaction management.
            orderType (str): Specifies the type of order ('open' or 'close') being cancelled.
            message (str): A message explaining the reason for the cancellation.
        """
        self.orderCancelled = True
        execOrder = self[f"{orderType}Order"]
        orderTransactionIds = execOrder.transactionIds
        context.logger.info(f"  >>>  CANCEL-----> {orderType} order with message: {message}")
        context.logger.debug("Expired or the limit order was not filled in the allocated time.")
        context.logger.info(f"Cancel {self.orderTag} & Progress of prices: {execOrder.priceProgressList}")
        context.logger.info(f"Position progress of prices: {self.priceProgressList}")
        context.charting.updateStats(self)
        for id in orderTransactionIds:
            context.logger.info(f"Canceling order: {id}")
            ticket = context.Transactions.GetOrderTicket(id)
            if ticket:
                ticket.Cancel()

    def summarize(self):
        """
        Returns a concise representation of the position with only essential fields.
        This is useful for logging purposes to avoid very verbose output.
        
        Returns:
            dict: A dictionary with essential position information
        """
        # Extract contract info from legs in a more informative way
        leg_info = []
        for leg in self.legs:
            leg_info.append({
                "strike": leg.strike,
                "contractSide": leg.contractSide,
                "isCall": leg.isCall if hasattr(leg, 'isCall') and leg.contract else None
            })
        
        # Create summary dict with essential fields
        summary = {
            "orderId": self.orderId,
            "orderTag": self.orderTag,
            "strategyId": self.strategyId,
            "strategyTag": self.strategyTag,
            "expiryStr": self.expiryStr,
            "legs": leg_info,
            "filled": self.filled,
            "orderCancelled": self.orderCancelled,
            "openOrder": {
                "filled": self.openOrder.filled,
                "fills": self.openOrder.fills,
                "limitPrice": self.openOrder.limitOrderPrice,
                "midPrice": self.openOrder.midPrice
            }
        }
        
        # Add DIT (days in trade) if the position has been opened
        if self.openDttm:
            summary["DIT"] = self.DIT
            
        # Add PnL information if available
        if self.PnL != 0.0:
            summary["PnL"] = self.PnL
            
        return summary
