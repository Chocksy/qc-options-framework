#region imports
from AlgorithmImports import *
#endregion

from Tools import ContractUtils, Logger, Underlying


# Your New Python File
class LimitOrderHandler:
    def __init__(self, context, base):
        self.context = context
        self.contractUtils = ContractUtils(context)
        self.base = base
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
            """
            IMPORTANT!!:
            Why do we cancel?
            If we update the ticket with the new price then we risk execution while updating the price of the rest of the combo order causing discrepancies.
            """
            for id in orderTransactionIds:
                ticket = context.Transactions.GetOrderTicket(id)
                ticket.Cancel('Cancelled trade and trying with new prices')
            # store when we last canceled/retried and check with current time if like 2-3 minutes passed before we retry again.
            self.makeLimitOrder(position, order, retry = True)
            # NOTE: If combo limit orders will execute limit orders instead of market orders then let's use this method.
            # self.updateComboLimitOrder(position, orderTransactionIds)
        elif not orderTransactionIds:
            self.makeLimitOrder(position, order)

        # Stop the timer
        self.context.executionTimer.stop()

    def makeLimitOrder(self, position, order, retry = False):
        context = self.context
        # Get the Limit order details
        # Get the order type: open|close
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

        # Define the legs of the combo order
        legs = []
        isComboOrder = len(contracts) > 1

        # Log the parameters used to validate the order
        self.logger.debug(f"Executing Limit Order to {orderType} the position:")
        self.logger.debug(f" - orderType: {orderType}")
        self.logger.debug(f" - orderTag: {orderTag}")
        self.logger.debug(f" - underlyingPrice: {Underlying(context, position.underlyingSymbol()).Price()}")
        self.logger.debug(f" - strikes: {[c.Strike for c in contracts]}")
        self.logger.debug(f" - orderQuantity: {orderQuantity}")
        self.logger.debug(f" - midPrice: {execOrder.midPrice}  (limitOrderPrice: {limitOrderPrice})")
        self.logger.debug(f" - bidAskSpread: {execOrder.bidAskSpread}")

        # Calculate the adjustment value based on the difference between the limit price and the total midPrice
        # TODO: this might have to be changed if we start buying options instead of selling for premium.
        if orderType == "close":
            adjustmentValue = self.calculateAdjustmentValueBought(
                execOrder=execOrder,
                limitOrderPrice=limitOrderPrice, 
                retries=order.fillRetries, 
                nrContracts=len(contracts)
            )
        else:
            adjustmentValue = self.calculateAdjustmentValueSold(
                execOrder=execOrder,
                limitOrderPrice=limitOrderPrice, 
                retries=order.fillRetries, 
                nrContracts=len(contracts)
            )
        # IMPORTANT!! Because ComboLimitOrder right now still executes market orders we should not use it. We need to use ComboLegLimitOrder and that will work.
        for n, contract in enumerate(contracts):
            # Set the order side: -1 -> Sell, +1 -> Buy
            orderSide = orderSign * orderSides[n]
            if orderSide != 0:
                newLimitPrice = self.contractUtils.midPrice(contract) + adjustmentValue if orderSide == -1 else self.contractUtils.midPrice(contract) - adjustmentValue
                # round the price or we get an error like:
                # Adjust the limit price to meet brokerage precision requirements
                increment = self.base.adjustmentIncrement if self.base.adjustmentIncrement is not None else 0.05
                newLimitPrice = round(newLimitPrice / increment) * increment
                newLimitPrice = round(newLimitPrice, 1)  # Ensure the price is rounded to two decimal places
                newLimitPrice = max(newLimitPrice, increment) # make sure the price is never 0. At least the increment.
                self.logger.info(f"{orderType.upper()} {orderQuantity} {orderTag}, {contract.Symbol}, newLimitPrice: {newLimitPrice}")

                if isComboOrder:
                    legs.append(Leg.Create(contract.Symbol, orderSide, newLimitPrice))
                else:
                    newTicket = context.LimitOrder(contract.Symbol, orderQuantity, newLimitPrice, tag=orderTag)
                    execOrder.transactionIds = [newTicket.OrderId]

        log_message = f"{orderType.upper()} {orderQuantity} {orderTag}, "
        log_message += f"{[c.Strike for c in contracts]} @ Mid: {round(execOrder.midPrice, 2)}, "
        log_message += f"NewLimit: {round(sum([l.OrderPrice * l.Quantity for l in legs]), 2)}, "
        log_message += f"Limit: {round(limitOrderPrice, 2)}, "
        log_message += f"DTTM: {execOrder.limitOrderExpiryDttm}, "
        log_message += f"Spread: ${round(execOrder.bidAskSpread, 2)}, "
        log_message += f"Bid & Ask: {[(round(self.contractUtils.bidPrice(c), 2), round(self.contractUtils.askPrice(c),2)) for c in contracts]}, "
        log_message += f"Volume: {[self.contractUtils.volume(c) for c in contracts]}, "
        log_message += f"OpenInterest: {[self.contractUtils.openInterest(c) for c in contracts]}"
        
        if orderType.lower() == 'close':
            log_message += f", Reason: {position.closeReason}"
        # To limit logs just log every 25 minutes
        self.logger.info(log_message)

        ### for contract in contracts
        if isComboOrder:
            # Execute by using a multi leg order if we have multiple sides.
            newTicket = context.ComboLegLimitOrder(legs, orderQuantity, tag=orderTag)
            execOrder.transactionIds = [t.OrderId for t in newTicket]
        # Store the last retry on this order. This is not ideal but the only way to handle combo limit orders on QC as the comboLimitOrder and all the others
        # as soon as you update one leg it will execute and mess it up.
        if retry:
            order.lastRetry = context.Time
            order.fillRetries += 1 # increment the number of fill tries

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
            step = execOrder.bidAskSpread / self.base.maxRetries
        else:
            step = self.base.adjustmentIncrement

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
            step = execOrder.bidAskSpread / self.base.maxRetries
        else:
            step = self.base.adjustmentIncrement

        # Round the target price to the nearest multiple of adjustmentIncrement
        target_price = round(target_price / step) * step

        # Calculate the adjustment value
        adjustment_value = (target_price - execOrder.midPrice) / nrContracts

        return adjustment_value
    
    """
    def updateComboLimitOrder(self, position, orderTransactionIds):
        context = self.context

        for id in orderTransactionIds:
            ticket = context.Transactions.GetOrderTicket(id)
            # store when we last canceled/retried and check with current time if like 2-3 minutes passed before we retry again.
            leg = next((leg for leg in position.legs if ticket.Symbol == leg.symbol), None)            contract = leg.contract
            # To update the limit price of the combo order, you only need to update the limit price of one of the leg orders.
            # The Update method returns an OrderResponse to signal the success or failure of the update request.
            if ticket and ticket.Status is not OrderStatus.Filled:
                newLimitPrice = self.contractUtils.midPrice(contract) + 0.1 if leg.isSold else self.contractUtils.midPrice(contract) - 0.1

                update_settings = UpdateOrderFields()
                update_settings.LimitPrice = newLimitPrice
                response = ticket.Update(update_settings)
                # Check if the update was successful
                if response.IsSuccess:
                    self.logger.debug(f"Order updated successfully for {ticket.Symbol}")
    """
    