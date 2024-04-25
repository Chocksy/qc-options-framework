from AlgorithmImports import *

"""
Started discussion on this here: https://chat.openai.com/chat/b5be32bf-850a-44ba-80fc-44f79a7df763
Use like this in main.py file:

percent_of_spread = 0.5
timeout = timedelta(minutes=2)
self.SetExecution(SmartPricingExecutionModel(percent_of_spread, timeout))
"""
class SmartPricingExecutionModel(ExecutionModel):
    def __init__(self, percent_of_spread, timeout):
        self.percent_of_spread = percent_of_spread
        self.timeout = timeout
        self.order_tickets = dict()

    def Execute(self, algorithm, targets):
        for target in targets:
            symbol = target.Symbol
            quantity = target.Quantity

            # If an order already exists for the symbol, skip
            if symbol in self.order_tickets:
                continue

            # Get the bid-ask spread and apply the user-defined percentage
            security = algorithm.Securities[symbol]
            if security.BidPrice != 0 and security.AskPrice != 0:
                spread = security.AskPrice - security.BidPrice
                adjusted_spread = spread * self.percent_of_spread

                if quantity > 0:
                    limit_price = security.BidPrice + adjusted_spread
                else:
                    limit_price = security.AskPrice - adjusted_spread

                # Submit the limit order with the calculated price
                ticket = algorithm.LimitOrder(symbol, quantity, limit_price)
                self.order_tickets[symbol] = ticket

                # Set the order expiration
                expiration = algorithm.UtcTime + self.timeout
                # ticket.Update(new UpdateOrderFields { TimeInForce = TimeInForce.GoodTilDate(expiration) })

    def OnOrderEvent(self, algorithm, order_event):
        if order_event.Status.IsClosed():
            order = algorithm.Transactions.GetOrderById(order_event.OrderId)
            symbol = order.Symbol
            if symbol in self.order_tickets:
                del self.order_tickets[symbol]
