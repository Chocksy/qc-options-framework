# region imports
from AlgorithmImports import *
# endregion

from datetime import datetime

class ProviderOptionContract:
    def __init__(self, symbol, underlying_price, context):
        self.symbol = symbol
        self.Symbol = symbol
        self.Underlying = symbol.Underlying
        self.UnderlyingSymbol = symbol.Underlying
        self.ID = symbol.ID
        self.UnderlyingLastPrice = underlying_price
        self.security = context.Securities[symbol]
        self.context = context
    
    @property
    def Expiry(self):
        return self.ID.Date

    @property
    def Strike(self):
        return self.ID.StrikePrice

    @property
    def Right(self):
        return self.ID.OptionRight

    @property
    def BidPrice(self):
        return self.security.BidPrice

    @property
    def AskPrice(self):
        return self.security.AskPrice

    @property
    def LastPrice(self):
        return self.security.Price

    @property
    def IsTradable(self):
        return self.security.IsTradable

    @property
    def OpenInterest(self):
        return self.security.OpenInterest

    @property
    def implied_volatility(self):
        return self.security.iv.current.value if self.security.iv else 0

    # Add any other properties or methods you commonly use from OptionContract