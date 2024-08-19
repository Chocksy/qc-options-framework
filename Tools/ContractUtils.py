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
            Calculates and returns the bid-ask spread of the given option contract.
    """

    def __init__(self, context):
        self.context = context # Set the context
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel) # Set the logger

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
            contract: A contract object.

        Returns:
            float: The last known price of the underlying security, or the contract's own last price if
                   the underlying security is not available.
        """
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
        """
        Returns the security object associated with the given contract.

        Args:
            contract: A contract object.

        Returns:
            Security object: The security corresponding to the contract's symbol or the contract itself if
                             the symbol is not found in the Securities dictionary.
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

    def midPrice(self, contract):
        """
        Calculates and returns the mid-price of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            float: The mid-price of the option contract.
        """
        security = self.getSecurity(contract)
        return 0.5 * (security.BidPrice + security.AskPrice)

    def strikePrice(self, contract):
        """
        Returns the strike price of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            float: The strike price of the option contract.
        """
        security = self.getSecurity(contract)
        return security.symbol.ID.StrikePrice

    def expiryDate(self, contract):
        """
        Returns the expiry date of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            datetime.date: The expiry date of the option contract.
        """
        security = self.getSecurity(contract)
        return security.symbol.ID.Date

    def volume(self, contract):
        """
        Returns the trading volume of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            int: The trading volume of the option contract.
        """
        security = self.getSecurity(contract)
        return security.Volume

    def openInterest(self, contract):
        """
        Returns the open interest of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            int: The open interest of the option contract.
        """
        security = self.getSecurity(contract)
        return security.OpenInterest

    def delta(self, contract):
        """
        Returns the delta of the given option contract if available.

        Args:
            contract: An option contract object.

        Returns:
            float or None: The delta of the option contract, or None if not available.
        """
        return contract.BSMGreeks.Delta if hasattr(contract, 'BSMGreeks') else None

    def gamma(self, contract):
        """
        Returns the gamma of the given option contract if available.

        Args:
            contract: An option contract object.

        Returns:
            float or None: The gamma of the option contract, or None if not available.
        """
        return contract.BSMGreeks.Gamma if hasattr(contract, 'BSMGreeks') else None

    def theta(self, contract):
        """
        Returns the theta of the given option contract if available.

        Args:
            contract: An option contract object.

        Returns:
            float or None: The theta of the option contract, or None if not available.
        """
        return contract.BSMGreeks.Theta if hasattr(contract, 'BSMGreeks') else None

    def vega(self, contract):
        """
        Returns the vega of the given option contract if available.

        Args:
            contract: An option contract object.

        Returns:
            float or None: The vega of the option contract, or None if not available.
        """
        return contract.BSMGreeks.Vega if hasattr(contract, 'BSMGreeks') else None

    def rho(self, contract):
        """
        Returns the rho of the given option contract if available.

        Args:
            contract: An option contract object.

        Returns:
            float or None: The rho of the option contract, or None if not available.
        """
        return contract.BSMGreeks.Rho if hasattr(contract, 'BSMGreeks') else None

    def bidPrice(self, contract):
        """
        Returns the bid price of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            float: The bid price of the option contract.
        """
        security = self.getSecurity(contract)
        return security.BidPrice

    def askPrice(self, contract):
        """
        Returns the ask price of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            float: The ask price of the option contract.
        """
        security = self.getSecurity(contract)
        return security.AskPrice

    def bidAskSpread(self, contract):
        """
        Calculates and returns the bid-ask spread of the given option contract.

        Args:
            contract: An option contract object.

        Returns:
            float: The absolute difference between the ask price and the bid price of the option contract.
        """
        security = self.getSecurity(contract)
        return abs(security.AskPrice - security.BidPrice)
