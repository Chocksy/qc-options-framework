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

    def Call(self):
        context = self.context
        orderEvent = self.orderEvent

        context.executionTimer.start()

        if self.context.LiveMode:
            self.context.positions_store.store_positions()

        if not (orderEvent.Status == OrderStatus.Filled or orderEvent.Status == OrderStatus.PartiallyFilled):
            return

        position_info = self.getPositionFromOrderEvent()
        if position_info is None:
            return

        bookPosition, workingOrder, orderType, order = position_info

        if orderEvent.IsAssignment:
            self.logger.info(f" -> Processing assignment for position: {bookPosition.orderTag}")
            self.handleAssignment(bookPosition, orderEvent.Symbol)
            return

        self.logger.debug(f" -> Processing order id {bookPosition.orderId} (orderTag: {bookPosition.orderTag}  -  orderType: {orderType}  -  Expiry: {bookPosition.expiryStr})")

        contractInfo = Helper().findIn(
            bookPosition.legs,
            lambda c: c.symbol == orderEvent.Symbol
        )
        if contractInfo is None:
            return

        execOrder = bookPosition[f"{orderType}Order"]

        if order and hasattr(order, 'Tag') and re.search(" - Warning.*", order.Tag):
            self.logger.warning(order.Tag)
            execOrder.stalePrice = True
            bookPosition[f"{orderType}StalePrice"] = True

        if workingOrder:
            workingOrder.fills += abs(orderEvent.FillQuantity)

        execOrder.fills += abs(orderEvent.FillQuantity)
        execOrder.fillPrice -= np.sign(orderEvent.FillQuantity) * orderEvent.FillPrice
        transactionAmt = orderEvent.FillQuantity * orderEvent.FillPrice * 100

        if orderType == "open":
            bookPosition.openPremium -= transactionAmt
        else:
            bookPosition.closePremium -= transactionAmt

        positionQuantity = bookPosition.orderQuantity
        contractSides = np.array([c.contractSide for c in bookPosition.legs])
        Nlegs = sum(abs(contractSides))

        if execOrder.fills == Nlegs * positionQuantity:
            self.handleFullyFilledOrder(bookPosition, execOrder, orderType, workingOrder)

        if orderType == "close" and bookPosition.openOrder.filled and bookPosition.closeOrder.filled:
            self.handleClosedPosition(bookPosition, contractInfo.contract)

        context.executionTimer.stop()

    def getPositionFromOrderEvent(self):
        orderEventId = self.orderEvent.OrderId
        order = self.context.Transactions.GetOrderById(orderEventId)
        orderTag = re.sub(" - Warning.*", "", order.Tag)

        workingOrder = self.context.workingOrders.get(orderTag)
        openPosition = self.context.openPositions.get(orderTag)

        if openPosition is not None:
            bookPosition = self.context.allPositions[openPosition]
            orderType = workingOrder.orderType if workingOrder else "close"
            return bookPosition, workingOrder, orderType, order

        # If openPosition is None, search by symbol in allPositions
        orderEventSymbol = self.orderEvent.Symbol

        for position in self.context.allPositions.values():
            if any(leg.symbol == orderEventSymbol for leg in position.legs):
                orderType = "close"  # Assuming assignment is a closing event
                return position, None, orderType, order

        return None

    def handleAssignment(self, bookPosition, symbol):
        strategy_class = bookPosition.strategyModule()
        if hasattr(strategy_class, 'handleAssignment'):
            strategy_class.handleAssignment(self.context, bookPosition, symbol)
        else:
            self.logger.info(f"Strategy {bookPosition.strategy} does not have a handleAssignment method")

        self.logger.info(f"Handled assignment for position: {bookPosition.orderTag}")

    def handleFullyFilledOrder(self, bookPosition, execOrder, orderType, workingOrder):
        execOrder.filled = True
        bookPosition.updateOrderStats(self.context, orderType)
        if workingOrder:
            self.context.workingOrders.pop(bookPosition.orderTag, None)
        bookPosition[orderType + "FilledDttm"] = self.context.Time
        bookPosition[orderType + "OrderMidPrice"] = execOrder.midPrice

        orderTypeUpper = orderType.upper()
        premium = round(bookPosition[f'{orderType}Premium'], 2)
        fillPrice = round(execOrder.fillPrice, 2)
        message = f"  >>>  {orderTypeUpper}: {bookPosition.orderTag}, Premium: ${premium} @ ${fillPrice}"
        if orderTypeUpper == "CLOSE":
            PnL = round(bookPosition.PnL, 2)
            percentage = round(bookPosition.PnL / bookPosition.openPremium * 100, 2)
            message += f"; P&L: ${PnL} ({percentage}%)"

        self.logger.info(message)
        self.logger.info(f"Working order progress of prices: {execOrder.priceProgressList}")
        self.logger.info(f"Position progress of prices: {bookPosition.priceProgressList}")
        self.logger.debug(f"The {orderType} event happened:")
        self.logger.debug(f" - orderType: {orderType}")
        self.logger.debug(f" - orderTag: {bookPosition.orderTag}")
        self.logger.debug(f" - premium: ${bookPosition[f'{orderType}Premium']}")
        self.logger.debug(f" - {orderType} price: ${round(execOrder.fillPrice, 2)}")

        self.context.charting.plotTrade(bookPosition, orderType)

        if orderType == "open":
            self.context.statsUpdated = True
            self.context.lastOpenedDttm = self.context.Time
            execOrder.premium = bookPosition.openPremium / 100

    def handleClosedPosition(self, bookPosition, contract):
        # Calculate position PnL
        positionPnL = bookPosition.openPremium + bookPosition.closePremium
        bookPosition.PnL = positionPnL

        # Safely remove the position from openPositions if it exists
        if bookPosition.orderTag in self.context.openPositions:
            self.context.openPositions.pop(bookPosition.orderTag)
            self.context.logger.debug(f"Closed position: {bookPosition.orderTag} removed from openPositions.")
        else:
            self.context.logger.warning(f"Attempted to remove position {bookPosition.orderTag} but it was not found in openPositions.")

        # Calculate days to expiry (DTE) for the contract
        closeDte = (contract.Expiry.date() - self.context.Time.date()).days
        closeTradeInfo = {"orderTag": bookPosition.orderTag, "closeDte": closeDte}

        # Add trade info to recently closed positions list
        self.context.recentlyClosedDTE.append(closeTradeInfo)

        # Update charting statistics for the closed position
        self.context.charting.updateStats(bookPosition)


# ENDsection: handle order events from main.py
