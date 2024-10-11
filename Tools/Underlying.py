#region imports
from AlgorithmImports import *
#endregion

"""
    Underlying class for the Options Strategy Framework.
    This class is used to get the underlying price.

    Example:
        self.underlying = Underlying(self, self.underlyingSymbol)
        self.underlyingPrice = self.underlying.Price()
"""


class Underlying:
    def __init__(self, context, underlyingSymbol):
        self.context = context
        self.underlyingSymbol = underlyingSymbol

    def Security(self):
        return self.context.Securities[self.underlyingSymbol]

    # Returns the underlying symbol current price.
    def Price(self):
        return self.Security().Price

    def Close(self):
        return self.Security().Close

    def SecurityTradeBar(self):
        last_data = self.Security().get_last_data()
        if isinstance(last_data, QuoteBar):
            return last_data.collapse()
        return last_data
