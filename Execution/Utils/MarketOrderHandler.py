#region imports
from AlgorithmImports import *
#endregion

from Tools import ContractUtils, Logger, Underlying


class MarketOrderHandler:
    """
    Manages the execution of market orders.

    This handler is responsible for processing and executing market orders for trading positions,
    accommodating both individual and combination trades. It integrates with the order management system to execute orders based on dynamic market conditions and predefined
    strategy parameters.

    Attributes:
        context: The trading context.
        base: Base configuration for the handler.
        logger (Logger): Utility for logging order processes and operations.
        contractUtils (ContractUtils): Provides utilities for handling and processing contract-specific data and operations.
    """
    def __init__(self, context, base):
        self.context = context
        self.base = base
        self.contractUtils = ContractUtils(context)
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)

    def call(self, position, order):
        """
        Processes and executes a market order for the specified trading position.
        This method starts by updating and verifying the order details, adjusts based on the current market status,
        and sends the order to the market. It logs all relevant order information.

        Args:
            position: The trading position for which the order is being placed.
            order: The order details including order type and quantity.

        """
        # Start the timer
        self.context.executionTimer.start()

        # Get the context
        context = self.context
        orderTag = position.orderTag
        orderQuantity = position.orderQuantity

        orderType = order.orderType
        contracts = [v.contract for v in position.legs]
        orderSides = [v.contractSide for v in position.legs]
        bidAskSpread = sum(list(map(self.contractUtils.bidAskSpread, contracts)))
        midPrice = sum(side * self.contractUtils.midPrice(contract) for side, contract in zip(orderSides, contracts))
        underlying = Underlying(context, position.underlyingSymbol())
        orderSign = 2 * int(orderType == "open") - 1
        execOrder = position[f"{orderType}Order"]
        execOrder.midPrice = midPrice

        # Check if the order already has transaction IDs
        orderTransactionIds = execOrder.transactionIds
        if orderTransactionIds:
            self.logger.debug(f"Market order already placed. Waiting for execution. Transaction IDs: {orderTransactionIds}")
            return

        # This updates prices and stats for the order
        position.updateOrderStats(context, orderType)
        # This updates the stats for the position
        position.updateStats(context, orderType)

        # Keep track of the midPrices of this order for faster debugging
        execOrder.priceProgressList.append(round(midPrice, 2))

        isComboOrder = len(position.legs) > 1
        legs = []
        # Loop through all contracts
        for contract in position.legs:
            # Get the order side
            orderSide = contract.contractSide * orderSign
            # Get the order quantity
            quantity = contract.quantity
            # Get the contract symbol
            symbol = contract.symbol
            # Get the contract object
            security = context.Securities[symbol]
            # get the target
            target = next(t for t in order.targets if t.Symbol == symbol)
            # calculate remaining quantity to be ordered
            # quantity = OrderSizing.GetUnorderedQuantity(context, target, security)

            self.logger.debug(f"{orderType} contract {symbol}:")
            self.logger.debug(f" - orderSide: {orderSide}")
            self.logger.debug(f" - quantity: {quantity}")
            self.logger.debug(f" - orderTag: {orderTag}")

            if orderSide != 0:
                if isComboOrder:
                    # If we are doing market orders, we need to create the legs of the combo order
                    legs.append(Leg.Create(symbol, orderSide))
                else:
                    # Send the Market order (asynchronous = True -> does not block the execution in case of partial fills)
                    context.MarketOrder(
                        symbol,
                        orderSide * quantity,
                        asynchronous=True,
                        tag=orderTag
                    )
        ### Loop through all contracts

        # Log the parameters used to validate the order
        log_message = f"{orderType.upper()} {orderQuantity} {orderTag}, "
        log_message += f"{[c.Strike for c in contracts]} @ Mid: {round(midPrice, 2)}"
        if orderType.lower() == 'close':
            log_message += f", Reason: {position.closeReason}"
        self.logger.info(log_message)

        self.logger.debug(f"Executing Market Order to {orderType} the position:")
        self.logger.debug(f" - orderType: {orderType}")
        self.logger.debug(f" - orderTag: {orderTag}")
        self.logger.debug(f" - underlyingPrice: {underlying.Price()}")
        self.logger.debug(f" - strikes: {[c.Strike for c in contracts]}")
        self.logger.debug(f" - orderQuantity: {orderQuantity}")
        self.logger.debug(f" - midPrice: {midPrice}")
        self.logger.debug(f" - bidAskSpread: {bidAskSpread}")

        # Execute only if we have multiple legs (sides) per order and no existing transaction IDs
        if (
            len(legs) > 0
            and not orderTransactionIds
            # Validate the bid-ask spread to make sure it's not too wide
            and not (position.strategyParam("validateBidAskSpread") and abs(bidAskSpread) > position.strategyParam("bidAskSpreadRatio")*abs(midPrice))
        ):
            order_result = context.ComboMarketOrder(
                legs,
                orderQuantity,
                asynchronous=True,
                tag=orderTag
            )
            execOrder.transactionIds = [t.OrderId for t in order_result]

        # Stop the timer
        self.context.executionTimer.stop()