#region imports
from AlgorithmImports import *
#endregion

from Tools import ContractUtils, Logger, Underlying, BSM


# Your New Python File
class LimitOrderHandlerWithCombo:
    def __init__(self, context, base):
        self.context = context
        self.contractUtils = ContractUtils(context)
        self.base = base
        self.bsm = BSM(context)
        # Set the logger
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)

    def call(self, position, order):
        # Start the timer
        self.context.executionTimer.start()

        # Get the context
        context = self.context

        # Get the Limit order details
        # Get the order type: open|close
        orderType = order.orderType

        # This updates prices and stats for the order
        position.updateOrderStats(context, orderType)
        # This updates the stats for the position
        position.updateStats(context, orderType)
        execOrder = position[f"{orderType}Order"]

        ticket = None
        orderTransactionIds = execOrder.transactionIds
        self.logger.debug(f"orderTransactionIds: {orderTransactionIds}")
        self.logger.debug(f"order.lastRetry: {order.lastRetry}")
        self.logger.debug(f"self.sinceLastRetry(context, order, timedelta(minutes = 1)): {self.sinceLastRetry(context, order, timedelta(minutes = 1))}")

        # Exit if we are not at the right scheduled interval
        if orderTransactionIds and (order.lastRetry is None or self.sinceLastRetry(context, order, timedelta(minutes = 1))):
            self.updateComboLimitOrder(position, order, orderTransactionIds)
        elif not orderTransactionIds:
            self.makeLimitOrder(position, order)

        # Stop the timer
        self.context.executionTimer.stop()

    def makeLimitOrder(self, position, order, retry = False):
        context = self.context
        orderType = order.orderType
        limitOrderPrice = self.limitOrderPrice(order)
        execOrder = position[f"{orderType}Order"]

        # Keep track of the midPrices of this order for faster debugging
        execOrder.priceProgressList.append(round(execOrder.midPrice, 2))
        orderTag = position.orderTag
        # Get the contracts
        contracts = [v.contract for v in position.legs]
        # Get the order quantity
        orderQuantity = position.orderQuantity
        # Sign of the order: open -> 1 (use orderSide as is),  close -> -1 (reverse the orderSide)
        orderSign = 2 * int(orderType == "open") - 1
        # Get the order sides
        orderSides = np.array([c.contractSide for c in position.legs])
        # Set the Greeks for the contracts maily for display/logging
        self.bsm.setGreeks(contracts)

        # Define the legs of the combo order
        legs = []

        for n, contract in enumerate(contracts):
            # Set the order side: -1 -> Sell, +1 -> Buy
            orderSide = orderSign * orderSides[n]
            if orderSide != 0:
                legs.append(Leg.Create(contract.Symbol, orderSide))

        # Calculate the new limit price
        newLimitPrice = self.calculateNewLimitPrice(position, execOrder, limitOrderPrice, order.fillRetries, len(contracts), orderType)

        # Log the parameters used to validate the order
        self.logOrderDetails(position, order)

        # Execute the combo limit order
        newTicket = context.ComboLimitOrder(legs, orderQuantity, newLimitPrice, tag=orderTag)
        execOrder.transactionIds = [t.OrderId for t in newTicket]

        # Log the order execution
        self.logOrderExecution(position, order, newLimitPrice)

        # Update order information if it's a retry
        if retry:
            order.lastRetry = context.Time
            order.fillRetries += 1

    def updateComboLimitOrder(self, position, order, orderTransactionIds):
        context = self.context
        orderType = order.orderType
        execOrder = position[f"{orderType}Order"]

        # Calculate the new limit price
        limitOrderPrice = self.limitOrderPrice(order)
        newLimitPrice = self.calculateNewLimitPrice(position, execOrder, limitOrderPrice, order.fillRetries, len(position.legs), orderType)

        # Get the first order ticket (we only need to update one for the combo order)
        ticket = context.Transactions.GetOrderTicket(orderTransactionIds[0])
        
        if ticket and ticket.Status != OrderStatus.Filled:
            update_settings = UpdateOrderFields()
            update_settings.LimitPrice = newLimitPrice
            response = ticket.Update(update_settings)
            
            if response.IsSuccess:
                self.logger.debug(f"Combo order updated successfully. New limit price: {newLimitPrice}")
            else:
                self.logger.warning(f"Failed to update combo order: {response.ErrorCode}")

        # Log the update
        self.logOrderExecution(position, order, newLimitPrice, action="UPDATED")

        # Update order information
        order.lastRetry = context.Time
        order.fillRetries += 1  # increment the number of fill tries

    def calculateNewLimitPrice(self, position, execOrder, limitOrderPrice, retries, nrContracts, orderType):
        if orderType == "close":
            adjustmentValue = self.calculateAdjustmentValueBought(
                execOrder=execOrder,
                limitOrderPrice=limitOrderPrice, 
                retries=retries, 
                nrContracts=nrContracts
            )
        else:
            adjustmentValue = self.calculateAdjustmentValueSold(
                execOrder=execOrder,
                limitOrderPrice=limitOrderPrice, 
                retries=retries, 
                nrContracts=nrContracts
            )

        # Determine if it's a credit or debit strategy
        isCredit = position.isCreditStrategy

        if isCredit:
            # For credit strategies, we want to receive at least this much (negative value)
            newLimitPrice = -(abs(execOrder.midPrice) - adjustmentValue) if orderType == "open" else -(abs(execOrder.midPrice) + adjustmentValue)
        else:
            # For debit strategies, we're willing to pay up to this much (positive value)
            newLimitPrice = execOrder.midPrice + adjustmentValue if orderType == "open" else execOrder.midPrice - adjustmentValue

        # Adjust the limit price to meet brokerage precision requirements
        increment = self.base.adjustmentIncrement if self.base.adjustmentIncrement is not None else 0.05
        newLimitPrice = round(newLimitPrice / increment) * increment
        newLimitPrice = round(newLimitPrice, 2)  # Ensure the price is rounded to two decimal places

        # Ensure the price is never 0 and maintains the correct sign
        if isCredit:
            newLimitPrice = min(newLimitPrice, -increment)
        else:
            newLimitPrice = max(newLimitPrice, increment)

        return newLimitPrice

    def logOrderDetails(self, position, order):
        orderType = order.orderType
        execOrder = position[f"{orderType}Order"]
        contracts = [v.contract for v in position.legs]

        self.logger.debug(f"Executing Limit Order to {orderType} the position:")
        self.logger.debug(f" - orderType: {orderType}")
        self.logger.debug(f" - orderTag: {position.orderTag}")
        self.logger.debug(f" - underlyingPrice: {Underlying(self.context, position.underlyingSymbol()).Price()}")
        self.logger.debug(f" - strikes: {[c.Strike for c in contracts]}")
        self.logger.debug(f" - orderQuantity: {position.orderQuantity}")
        self.logger.debug(f" - midPrice: {execOrder.midPrice}  (limitOrderPrice: {self.limitOrderPrice(order)})")
        self.logger.debug(f" - bidAskSpread: {execOrder.bidAskSpread}")

    def logOrderExecution(self, position, order, newLimitPrice, action=None):
        orderType = order.orderType
        execOrder = position[f"{orderType}Order"]
        contracts = [v.contract for v in position.legs]

        action = action or orderType.upper()
        orderLimitPrice = self.limitOrderPrice(order)
        if position.isCreditStrategy:
            orderLimitPrice = -orderLimitPrice

        log_message = f"{action} {position.orderQuantity} {position.orderTag}, "
        log_message += f"{[c.Strike for c in contracts]} @ Mid: {round(execOrder.midPrice, 2)}, "
        log_message += f"NewLimit: {round(newLimitPrice, 2)}, "
        log_message += f"Limit: {round(orderLimitPrice, 2)}, "
        log_message += f"DTTM: {execOrder.limitOrderExpiryDttm}, "
        log_message += f"Spread: ${round(execOrder.bidAskSpread, 2)}, "
        log_message += f"Bid & Ask: {[(round(self.contractUtils.bidPrice(c), 2), round(self.contractUtils.askPrice(c),2)) for c in contracts]}, "
        log_message += f"Volume: {[self.contractUtils.volume(c) for c in contracts]}, "
        log_message += f"OpenInterest: {[self.contractUtils.openInterest(c) for c in contracts]}, "
        log_message += f"Delta: {[round(self.contractUtils.delta(c), 2) for c in contracts]}"

        if orderType.lower() == 'close':
            log_message += f", Reason: {position.closeReason}"
        # To limit logs just log every 25 minutes
        self.logger.info(log_message)

    def limitOrderPrice(self, order):
        orderType = order.orderType
        limitOrderPrice = order.limitOrderPrice
        # Just use a default limit price that is supposed to be the smallest prossible.
        # The limit order price of 0 can happen if the trade is worthless.
        if limitOrderPrice == 0 and orderType == 'close':
            limitOrderPrice = 0.05

        return limitOrderPrice

    def sinceLastRetry(self, context, order, frequency = timedelta(minutes = 3)):
        if order.lastRetry is None: return True

        timeSinceLastRetry = context.Time - order.lastRetry
        minutesSinceLastRetry = timedelta(minutes = round(timeSinceLastRetry.seconds / 60))
        return minutesSinceLastRetry % frequency == timedelta(minutes=0)

    def calculateAdjustmentValueSold(self, execOrder, limitOrderPrice, retries=0, nrContracts=1):
        if self.base.orderAdjustmentPct is None and self.base.adjustmentIncrement is None:
            raise ValueError("orderAdjustmentPct or adjustmentIncrement must be set in the parameters")

        # Adjust the limitOrderPrice
        limitOrderPrice += self.base.orderAdjustmentPct * limitOrderPrice # Increase the price by orderAdjustmentPct

        min_price = self.base.minPricePct * limitOrderPrice # Minimum allowed price is % of limitOrderPrice

        # Calculate the range and step
        if self.base.adjustmentIncrement is None:
            # Calculate the step based on the bidAskSpread and the number of retries
            step = execOrder.bidAskSpread / retries
        else:
            step = self.base.adjustmentIncrement

        step = max(step, 0.01) # Ensure the step is at least 0.01

        # Start with the preferred price
        target_price = execOrder.midPrice + step

        # If we have retries, adjust the target price accordingly
        if retries > 0:
            target_price -= retries * step

        # Ensure the target price does not fall below the minimum limit
        if target_price < min_price:
            target_price = min_price

        # Round the target price to the nearest multiple of adjustmentIncrement
        target_price = round(target_price / step) * step

        # Calculate the adjustment value
        adjustment_value = (target_price - execOrder.midPrice) / nrContracts

        return adjustment_value

    def calculateAdjustmentValueBought(self, execOrder, limitOrderPrice, retries=0, nrContracts=1):
        if self.base.orderAdjustmentPct is None and self.base.adjustmentIncrement is None:
            raise ValueError("orderAdjustmentPct or adjustmentIncrement must be set in the parameters")

        # Adjust the limitOrderPrice
        limitOrderPrice += self.base.orderAdjustmentPct * limitOrderPrice # Increase the price by orderAdjustmentPct

        increment = self.base.retryChangePct * limitOrderPrice  # Increment value for each retry
        max_price = self.base.minPricePct * limitOrderPrice # Maximum allowed price is % of limitOrderPrice

        # Start with the preferred price
        target_price = max_price

        # If we have retries, increment the target price accordingly
        if retries > 0:
            target_price += retries * increment

        # Ensure the target price does not exceed the maximum limit
        if target_price > limitOrderPrice:
            target_price = limitOrderPrice

        # Calculate the range and step
        if self.base.adjustmentIncrement is None:
            # Calculate the step based on the bidAskSpread and the number of retries
            step = execOrder.bidAskSpread / retries
        else:
            step = self.base.adjustmentIncrement

        # Round the target price to the nearest multiple of adjustmentIncrement
        target_price = round(target_price / step) * step

        # Calculate the adjustment value
        adjustment_value = (target_price - execOrder.midPrice) / nrContracts

        return adjustment_value
    
