#region imports
from AlgorithmImports import *
#endregion

from .Logger import Logger


class ContractUtils:
    """
    Utility class for handling contract-related operations and retrieving contract details.
    This class provides methods to extract and compute various properties and metrics related to financial
    contracts. It interacts with the provided context to fetch current market data and perform operations
    related to securities and contracts.
    Attributes:
        context: An object providing access to market data and securities.
        logger: An instance of Logger used for logging operations.
    Methods:
        getUnderlyingPrice(symbol):
            Returns the latest price of the security associated with the given symbol.
        
        getUnderlyingLastPrice(contract):
            Retrieves the last known price of the underlying security of the given contract.
        
        getSecurity(contract):
            Returns the security object associated with the given contract.
        
        midPrice(contract):
            Calculates and returns the mid-price of the given option contract.
        
        strikePrice(contract):
            Returns the strike price of the given option contract.
        
        expiryDate(contract):
            Returns the expiry date of the given option contract.
        
        volume(contract):
            Returns the trading volume of the given option contract.
        
        openInterest(contract):
            Returns the open interest of the given option contract.
        
        delta(contract):
            Returns the delta of the given option contract if available.
        
        gamma(contract):
            Returns the gamma of the given option contract if available.
        
        theta(contract):
            Returns the theta of the given option contract if available.
        
        vega(contract):
            Returns the vega of the given option contract if available.
        
        rho(contract):
            Returns the rho of the given option contract if available.
        
        bidPrice(contract):
            Returns the bid price of the given option contract.
        
        askPrice(contract):
            Returns the ask price of the given option contract.
        
        bidAskSpread(contract):
            Calculates and returns the bid-ask spread of the given option
    """

    def __init__(self, context, custom_greeks=False):
        self.context = context # Set the context
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel) # Set the logger
        self.custom_greeks = custom_greeks

    def getUnderlyingPrice(self, symbol):
        """
        Returns the latest price of the security associated with the given symbol.
        Args:
            symbol (str): The symbol of the security.
        Returns:
            float: The last known price of the security.
        """
        security = self.context.Securities[symbol]
        return self.context.GetLastKnownPrice(security).Price

    def getUnderlyingLastPrice(self, contract):
        """
        Retrieves the last known price of the underlying security of the given contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The last known price of the underlying security.
        """
        # Get the context
        context = self.context
        security = None
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
        """
        Retrieves the security object associated with the given contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            Security: The security object associated with the contract.
        """
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
        """
        Calculates and returns the mid-price of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The mid-price of the contract.
        """
        security = self.getSecurity(contract)
        return 0.5 * (security.BidPrice + security.AskPrice)
    
    # Returns the mid-price of an option contract
    def strikePrice(self, contract):
        """
        Retrieves the strike price of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The strike price of the contract.
        """
        security = self.getSecurity(contract)
        return security.symbol.ID.StrikePrice
    
    def expiryDate(self, contract):
        """
        Retrieves the expiry date of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            datetime: The expiry date of the contract.
        """
        security = self.getSecurity(contract)
        return security.symbol.ID.Date
    
    def volume(self, contract):
        """
        Retrieves the trading volume of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            int: The trading volume of the contract.
        """
        security = self.getSecurity(contract)
        return security.Volume
    
    def openInterest(self, contract):
        """
        Retrieves the open interest of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            int: The open interest of the contract.
        """
        security = self.getSecurity(contract)
        return security.OpenInterest

    def implied_volatility(self, contract):
        """
        Retrieves the implied volatility of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The implied volatility of the contract.
        """
        return contract.implied_volatility

    def delta(self, contract):
        """
        Retrieves the delta of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The delta of the contract.
        """
        if self.custom_greeks:
            return contract.BSMGreeks.Delta if hasattr(contract, 'BSMGreeks') else contract.greeks.delta
        return contract.greeks.delta 

    def gamma(self, contract):
        """
        Retrieves the gamma of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The gamma of the contract.
        """
        if self.custom_greeks:
            return contract.BSMGreeks.Gamma if hasattr(contract, 'BSMGreeks') else contract.greeks.gamma
        return contract.greeks.gamma 

    def theta(self, contract):
        """
        Retrieves the theta of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The theta of the contract.
        """
        if self.custom_greeks:
            return contract.BSMGreeks.Theta if hasattr(contract, 'BSMGreeks') else contract.greeks.theta
        return contract.greeks.theta 

    def vega(self, contract):
        """
        Retrieves the vega of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The vega of the contract.
        """
        if self.custom_greeks:
            return contract.BSMGreeks.Vega if hasattr(contract, 'BSMGreeks') else contract.greeks.vega
        return contract.greeks.vega 

    def rho(self, contract):
        """
        Retrieves the rho of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The rho of the contract.
        """
        if self.custom_greeks:
            return contract.BSMGreeks.Rho if hasattr(contract, 'BSMGreeks') else contract.greeks.rho
        return contract.greeks.rho 
        
    def bidPrice(self, contract):
        """
        Retrieves the bid price of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The bid price of the contract.
        """
        security = self.getSecurity(contract)
        return security.BidPrice

    def askPrice(self, contract):
        """
        Retrieves the ask price of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The ask price of the contract.
        """
        security = self.getSecurity(contract)
        return security.AskPrice

    def bidAskSpread(self, contract):
        """
        Calculates and returns the bid-ask spread of the given option contract.
        Args:
            contract (Contract): The contract object.
        Returns:
            float: The bid-ask spread of the contract.
        """
        security = self.getSecurity(contract)
        return abs(security.AskPrice - security.BidPrice)