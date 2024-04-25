#region imports
from AlgorithmImports import *
#endregion

import re
import numpy as np
from Tools import Logger, Helper


"""
Details about order types:
/// New order pre-submission to the order processor (0)
New = 0,
/// Order submitted to the market (1)
Submitted = 1,
/// Partially filled, In Market Order (2)
PartiallyFilled = 2,
/// Completed, Filled, In Market Order (3)
Filled = 3,
/// Order cancelled before it was filled (5)
Canceled = 5,
/// No Order State Yet (6)
None = 6,
/// Order invalidated before it hit the market (e.g. insufficient capital) (7)
Invalid = 7,
/// Order waiting for confirmation of cancellation (6)
CancelPending = 8,
/// Order update submitted to the market (9)
UpdateSubmitted = 9
"""


class HandleOrderEvents:
    def __init__(self, context, orderEvent):
        self.context = context
        self.orderEvent = orderEvent
        self.logger = Logger(self.context, className=type(self.context).__name__, logLevel=self.context.logLevel)

    # section: handle order events from main.py
    def Call(self):
        # Get the context
        context = self.context
        orderEvent = self.orderEvent

        # Start the timer
        context.executionTimer.start()

        # Process only Fill events
        if not (orderEvent.Status == OrderStatus.Filled or orderEvent.Status == OrderStatus.PartiallyFilled):
            return

        if(orderEvent.IsAssignment):
            # TODO: Liquidate the assigned position.
            #  Eventually figure out which open position it belongs to and close that position.
            return

        # Get the orderEvent id
        orderEventId = orderEvent.OrderId
        # Retrieve the order associated to this events
        order = context.Transactions.GetOrderById(orderEventId)
        # Get the order tag. Remove any warning text that might have been added in case of Fills at Stale Price
        orderTag = re.sub(" - Warning.*", "", order.Tag)

        # TODO: Additionally check for OTM Underlying order.Tag that would mean it expired worthless.
        # if orderEvent.FillPrice == 0.0:
        #     position = next((position for position in context.allPositions if any(leg.symbol == orderEvent.Symbol for leg in position.legs)), None)
        #     context.workingOrders.pop(position.orderTag)

        # Get the working order (if available)
        workingOrder = context.workingOrders.get(orderTag)
        # Exit if this order tag is not in the list of open orders.
        if workingOrder == None:
            return

        # Get the position from the openPositions
        openPosition = context.openPositions.get(orderTag)
        if openPosition is None:
            return
        # Retrieved the book position (this it the full entry inside allPositions that will be converted into a CSV record)
        # bookPosition = context.allPositions[orderId]
        bookPosition = context.allPositions[openPosition]

        contractInfo = Helper().findIn(
            bookPosition.legs,
            lambda c: c.symbol == orderEvent.Symbol
        )
        # Exit if we couldn't find the contract info.
        if contractInfo == None:
            return

        # Get the order id and expiryStr value for the contract
        orderId = bookPosition.orderId # contractInfo["orderId"]
        positionKey = bookPosition.orderTag # contractInfo["positionKey"]
        expiryStr = contractInfo.expiry # contractInfo["expiryStr"]
        orderType = workingOrder.orderType # contractInfo["orderType"]

        # Log the order event
        self.logger.debug(f" -> Processing order id {orderId} (orderTag: {orderTag}  -  orderType: {orderType}  -  Expiry: {expiryStr})")

        # Get the contract associated to this order event
        contract = contractInfo.contract # openPosition["contractDictionary"][orderEvent.Symbol]
        # Get the description associated with this contract
        contractDesc = contractInfo.key # openPosition["contractSideDesc"][orderEvent.Symbol]
        # Get the quantity used to open the position
        positionQuantity = bookPosition.orderQuantity # openPosition["orderQuantity"]
        # Get the side of each leg (-n -> Short, +n -> Long)
        contractSides = np.array([c.contractSide for c in bookPosition.legs]) # np.array(openPosition["sides"])
        # Leg Quantity
        legQuantity = abs(bookPosition.contractSide[orderEvent.Symbol])
        # Total legs quantity in the whole position
        Nlegs = sum(abs(contractSides))

        # get the position order block
        execOrder = bookPosition[f"{orderType}Order"]

        # Check if the contract was filled at a stale price (Warnings in the orderTag)
        if re.search(" - Warning.*", order.Tag):
            self.logger.warning(order.Tag)
            execOrder.stalePrice = True
            bookPosition[f"{orderType}StalePrice"] = True

        # Add the order to the list of openPositions orders (only if this is the first time the order is filled  - in case of partial fills)
        # if contractInfo["fills"] == 0:
        #     openPosition[f"{orderType}Order"]["orders"].append(order)

        # Update the number of filled contracts associated with this order
        workingOrder.fills += abs(orderEvent.FillQuantity)

        # Remove this order entry from the self.workingOrders[orderTag] dictionary if it has been fully filled
        # if workingOrder.fills == legQuantity * positionQuantity:
        #     removedOrder = context.workingOrders.pop(orderTag)
        #     # Update the stats of the given contract inside the bookPosition (reverse the sign of the FillQuantity: Sell -> credit, Buy -> debit)
        #     bookPosition.updateContractStats(openPosition, contract, orderType = orderType, fillPrice = - np.sign(orderEvent.FillQuantity) * orderEvent.FillPrice)

        # Update the counter of positions that have been filled
        execOrder.fills += abs(orderEvent.FillQuantity)
        execOrder.fillPrice -= np.sign(orderEvent.FillQuantity) * orderEvent.FillPrice
        # Get the total amount of the transaction
        transactionAmt = orderEvent.FillQuantity * orderEvent.FillPrice * 100

        # Check if this is a fill order for an entry position
        if orderType == "open":
            # Update the openPremium field to include the current transaction (use "-=" to reverse the side of the transaction: Short -> credit, Long -> debit)
            bookPosition.openPremium -= transactionAmt
        else: # This is an order for the exit position
            # Update the closePremium field to include the current transaction  (use "-=" to reverse the side of the transaction: Sell -> credit, Buy -> debit)
            bookPosition.closePremium -= transactionAmt

        # Check if all legs have been filled
        if execOrder.fills == Nlegs*positionQuantity:
            execOrder.filled = True
            bookPosition.updateOrderStats(context, orderType)
            # Remove the working order now that it has been filled
            context.workingOrders.pop(orderTag)
            # Set the time when the full order was filled
            bookPosition[orderType + "FilledDttm"] = context.Time
            # Record the order mid price
            bookPosition[orderType + "OrderMidPrice"] = execOrder.midPrice

            # All of this for the logger.info
            orderTypeUpper = orderType.upper()
            premium = round(bookPosition[f'{orderType}Premium'], 2)
            fillPrice = round(execOrder.fillPrice, 2)
            message = f"  >>>  {orderTypeUpper}: {orderTag}, Premium: ${premium} @ ${fillPrice}"
            if orderTypeUpper == "CLOSE":
                PnL = round(bookPosition.PnL, 2)
                percentage = round(bookPosition.PnL / bookPosition.openPremium * 100, 2)
                message += f"; P&L: ${PnL} ({percentage}%)"
            
            self.logger.info(message)            
            self.logger.info(f"Working order progress of prices: {execOrder.priceProgressList}")
            self.logger.info(f"Position progress of prices: {bookPosition.priceProgressList}")
            self.logger.debug(f"The {orderType} event happened:")
            self.logger.debug(f" - orderType: {orderType}")
            self.logger.debug(f" - orderTag: {orderTag}")
            self.logger.debug(f" - premium: ${bookPosition[f'{orderType}Premium']}")
            self.logger.debug(f" - {orderType} price: ${round(execOrder.fillPrice, 2)}")

            context.charting.plotTrade(bookPosition, orderType)

            if orderType == "open":
                # Trigger an update of the charts
                context.statsUpdated = True
                # Marks the date/time of the most recenlty opened position
                context.lastOpenedDttm = context.Time
                # Store the credit received (needed to determine the stop loss): value is per share (divided by 100)
                execOrder.premium = bookPosition.openPremium / 100

        # Check if the entire position has been closed
        if orderType == "close" and bookPosition.openOrder.filled and bookPosition.closeOrder.filled:

            # Compute P&L for the position
            positionPnL = bookPosition.openPremium + bookPosition.closePremium

            # Store the PnL for the position
            bookPosition.PnL = positionPnL
            # Now we can remove the position from the self.openPositions dictionary
            context.openPositions.pop(orderTag)

            # Compute the DTE at the time of closing the position
            closeDte = (contract.Expiry.date() - context.Time.date()).days
            # Collect closing trade info
            closeTradeInfo = {"orderTag": orderTag, "closeDte": closeDte}
            # Add this trade info to the FIFO list
            context.recentlyClosedDTE.append(closeTradeInfo)

            # ###########################
            # Collect Performance metrics
            # ###########################
            context.charting.updateStats(bookPosition)

        # Stop the timer
        context.executionTimer.stop()
# ENDsection: handle order events from main.py

