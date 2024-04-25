#region imports
from AlgorithmImports import *
#endregion

from .Logger import Logger


class ContractUtils:
    def __init__(self, context):
        # Set the context
        self.context = context
        # Set the logger
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)

    def getUnderlyingPrice(self, symbol):
        security = self.context.Securities[symbol]
        return self.context.GetLastKnownPrice(security).Price

    def getUnderlyingLastPrice(self, contract):
        # Get the context
        context = self.context
        # Get the object from the Securities dictionary if available (pull the latest price), else use the contract object itself
        if contract.UnderlyingSymbol in context.Securities:
            security = context.Securities[contract.UnderlyingSymbol]

        # Check if we have found the security
        if security is not None:
            # Get the last known price of the security
            return context.GetLastKnownPrice(security).Price
        else:
            # Get the UnderlyingLastPrice attribute of the contract
            return contract.UnderlyingLastPrice

    def getSecurity(self, contract):
        # Get the Securities object
        Securities = self.context.Securities
        # Check if we can extract the Symbol attribute
        if hasattr(contract, "Symbol") and contract.Symbol in Securities:
            # Get the security from the Securities dictionary if available (pull the latest price), else use the contract object itself
            security = Securities[contract.Symbol]
        else:
            # Use the contract itself
            security = contract
        return security

    # Returns the mid-price of an option contract
    def midPrice(self, contract):
        security = self.getSecurity(contract)
        return 0.5 * (security.BidPrice + security.AskPrice)
    
    def volume(self, contract):
        security = self.getSecurity(contract)
        return security.Volume
    
    def openInterest(self, contract):
        security = self.getSecurity(contract)
        return security.OpenInterest
    
    def delta(self, contract):
        security = self.getSecurity(contract)
        return security.Delta
    
    def gamma(self, contract):
        security = self.getSecurity(contract)
        return security.Gamma
    
    def theta(self, contract):
        security = self.getSecurity(contract)
        return security.Theta
    
    def vega(self, contract):
        security = self.getSecurity(contract)
        return security.Vega
    
    def rho(self, contract):
        security = self.getSecurity(contract)
        return security.Rho
    
    def bidPrice(self, contract):
        security = self.getSecurity(contract)
        return security.BidPrice
    
    def askPrice(self, contract):
        security = self.getSecurity(contract)
        return security.AskPrice

    def bidAskSpread(self, contract):
        security = self.getSecurity(contract)
        return abs(security.AskPrice - security.BidPrice)
