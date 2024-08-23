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

        if not (orderEvent.Status == OrderStatus.Filled or orderEvent.Status == OrderStatus.PartiallyFilled):
            return

        if orderEvent.IsAssignment:
            self.handleAssignment()
            return

        position_info = self.getPositionFromOrderEvent()
        if position_info is None:
            return

        bookPosition, workingOrder, orderType = position_info

        self.logger.debug(f" -> Processing order id {bookPosition.orderId} (orderTag: {bookPosition.orderTag}  -  orderType: {orderType}  -  Expiry: {bookPosition.expiryStr})")

        contractInfo = Helper().findIn(
            bookPosition.legs,
            lambda c: c.symbol == orderEvent.Symbol
        )
        if contractInfo is None:
            return

        execOrder = bookPosition[f"{orderType}Order"]

        if re.search(" - Warning.*", orderEvent.Tag):
            self.logger.warning(orderEvent.Tag)
            execOrder.stalePrice = True
            bookPosition[f"{orderType}StalePrice"] = True

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
        if workingOrder is None:
            return None

        openPosition = self.context.openPositions.get(orderTag)
        if openPosition is None:
            return None

        bookPosition = self.context.allPositions[openPosition]
        orderType = workingOrder.orderType

        return bookPosition, workingOrder, orderType

    def handleAssignment(self):
        position_info = self.getPositionFromOrderEvent()
        if position_info is None:
            return

        bookPosition, _, _ = position_info
        strategy_module = bookPosition.strategyModule()
        if hasattr(strategy_module, 'handleAssignment'):
            strategy_module.handleAssignment(self.context, bookPosition)
        else:
            self.logger.warning(f"Strategy {bookPosition.strategy} does not have a handleAssignment method")

        self.logger.info(f"Handled assignment for position: {bookPosition.orderTag}")

    def handleFullyFilledOrder(self, bookPosition, execOrder, orderType, workingOrder):
        execOrder.filled = True
        bookPosition.updateOrderStats(self.context, orderType)
        self.context.workingOrders.pop(bookPosition.orderTag)
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
        positionPnL = bookPosition.openPremium + bookPosition.closePremium
        bookPosition.PnL = positionPnL
        self.context.openPositions.pop(bookPosition.orderTag)

        closeDte = (contract.Expiry.date() - self.context.Time.date()).days
        closeTradeInfo = {"orderTag": bookPosition.orderTag, "closeDte": closeDte}
        self.context.recentlyClosedDTE.append(closeTradeInfo)

        self.context.charting.updateStats(bookPosition)

# ENDsection: handle order events from main.py