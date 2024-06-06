#region imports
from AlgorithmImports import *
#endregion

from .Underlying import Underlying
import operator

class DataHandler:
    # The supported cash indices by QC https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/tickdata/us-cash-indices#05-Supported-Indices
    # These need to be added using AddIndex instead of AddEquity
    CashIndices = ['VIX','SPX','NDX']

    def __init__(self, context, ticker, strategy):
        self.ticker = ticker
        self.context = context
        self.strategy = strategy

    # Method to add the ticker[String] data to the context.
    # @param resolution [Resolution]
    # @return [Symbol]
    def AddUnderlying(self, resolution=Resolution.Minute):
        if self.__CashTicker():
            return self.context.AddIndex(self.ticker, resolution=resolution)
        else:
            return self.context.AddEquity(self.ticker, resolution=resolution)

    # SECTION BELOW IS FOR ADDING THE OPTION CHAIN
    # Method to add the option chain data to the context.
    # @param resolution [Resolution]
    def AddOptionsChain(self, underlying, resolution=Resolution.Minute):
        if self.ticker == "SPX":
            # Underlying is SPX. We'll load and use SPXW and ignore SPX options (these close in the AM)
            return self.context.AddIndexOption(underlying.Symbol, "SPXW", resolution)
        elif self.__CashTicker():
            # Underlying is an index
            return self.context.AddIndexOption(underlying.Symbol, resolution)
        else:
            # Underlying is an equity
            return self.context.AddOption(underlying.Symbol, resolution)

    # Should be called on an option object like this: option.SetFilter(self.OptionFilter)
    # !This method is called every minute if the algorithm resolution is set to minute
    def SetOptionFilter(self, universe):
        # Start the timer
        self.context.executionTimer.start('Tools.DataHandler -> SetOptionFilter')
        self.context.logger.debug(f"SetOptionFilter -> universe: {universe}")
        # Include Weekly contracts
        # nStrikes contracts to each side of the ATM
        # Contracts expiring in the range (DTE-5, DTE)
        filteredUniverse = universe.Strikes(-self.strategy.nStrikesLeft, self.strategy.nStrikesRight)\
                                   .Expiration(max(0, self.strategy.dte - self.strategy.dteWindow), max(0, self.strategy.dte))\
                                   .IncludeWeeklys()
        self.context.logger.debug(f"SetOptionFilter -> filteredUniverse: {filteredUniverse}")
        # Stop the timer
        self.context.executionTimer.stop('Tools.DataHandler -> SetOptionFilter')

        return filteredUniverse

    # SECTION BELOW HANDLES OPTION CHAIN PROVIDER METHODS
    def optionChainProviderFilter(self, symbols, min_strike_rank, max_strike_rank, minDte, maxDte):
        self.context.executionTimer.start('Tools.DataHandler -> optionChainProviderFilter')
        self.context.logger.debug(f"optionChainProviderFilter -> symbols: {symbols}")
        # Check if we got any symbols to process
        if len(symbols) == 0:
            return None

        # Filter the symbols based on the expiry range
        filteredSymbols = [symbol for symbol in symbols
                            if minDte <= (symbol.ID.Date.date() - self.context.Time.date()).days <= maxDte
                          ]

        self.context.logger.debug(f"optionChainProviderFilter -> filteredSymbols: {filteredSymbols}")
        # Exit if there are no symbols for the selected expiry range
        if not filteredSymbols:
            return None

        # If this is not a cash ticker, filter out any non-tradable symbols.
        # to escape the error `Backtest Handled Error: The security with symbol 'SPY 220216P00425000' is marked as non-tradable.`
        if not self.__CashTicker():
            filteredSymbols = [x for x in filteredSymbols if self.context.Securities[x.ID.Symbol].IsTradable]

        underlying = Underlying(self.context, self.strategy.underlyingSymbol)
        # Get the latest price of the underlying
        underlyingLastPrice = underlying.Price()

        # Find the ATM strike
        atm_strike = sorted(filteredSymbols
                            ,key = lambda x: abs(x.ID.StrikePrice - underlying.Price())
                            )[0].ID.StrikePrice

        # Get the list of available strikes
        strike_list = sorted(set([i.ID.StrikePrice for i in filteredSymbols]))

        # Find the index of ATM strike in the sorted strike list
        atm_strike_rank = strike_list.index(atm_strike)
        # Get the Min and Max strike price based on the specified number of strikes
        min_strike = strike_list[max(0, atm_strike_rank + min_strike_rank + 1)]
        max_strike = strike_list[min(atm_strike_rank + max_strike_rank - 1, len(strike_list)-1)]

        # Get the list of symbols within the selected strike range
        selectedSymbols = [symbol for symbol in filteredSymbols
                                if min_strike <= symbol.ID.StrikePrice <= max_strike
                          ]
        self.context.logger.debug(f"optionChainProviderFilter -> selectedSymbols: {selectedSymbols}")
        # Loop through all Symbols and create a list of OptionContract objects
        contracts = []
        for symbol in selectedSymbols:
            # Create the OptionContract
            contract = OptionContract(symbol, symbol.Underlying)
            self.AddOptionContracts([contract], resolution = self.context.timeResolution)

            # Set the BidPrice
            contract.BidPrice = self.Securities[contract.Symbol].BidPrice
            # Set the AskPrice
            contract.AskPrice = self.Securities[contract.Symbol].AskPrice
            # Set the UnderlyingLastPrice
            contract.UnderlyingLastPrice = underlyingLastPrice
            # Add this contract to the output list
            contracts.append(contract)
        
        self.context.executionTimer.stop('Tools.DataHandler -> optionChainProviderFilter')
        
        # Return the list of contracts
        return contracts

    def getOptionContracts(self, slice):
        # Start the timer
        self.context.executionTimer.start('Tools.DataHandler -> getOptionContracts')

        contracts = None
        # Set the DTE range (make sure values are not negative)
        minDte = max(0, self.strategy.dte - self.strategy.dteWindow)
        maxDte = max(0, self.strategy.dte)
        self.context.logger.debug(f"getOptionContracts -> minDte: {minDte}")
        self.context.logger.debug(f"getOptionContracts -> maxDte: {maxDte}")
        # Loop through all chains
        for chain in slice.OptionChains:
            # Look for the specified optionSymbol
            if chain.Key != self.strategy.optionSymbol:
                continue
            # Make sure there are any contracts in this chain
            if chain.Value.Contracts.Count != 0:
                # Put the contracts into a list so we can cache the Greeks across multiple strategies
                contracts = [
                    contract for contract in chain.Value if minDte <= (contract.Expiry.date() - self.context.Time.date()).days <= maxDte
                ]
        self.context.logger.debug(f"getOptionContracts -> contracts: {contracts}")
        # If no chains were found, use OptionChainProvider to see if we can find any contracts
        # Only do this for short term expiration contracts (DTE < 3) where slice.OptionChains usually fails to retrieve any chains
        # We don't want to do this all the times for performance reasons
        if contracts == None and self.strategy.dte < 3:
            # Get the list of available option Symbols
            symbols = self.context.OptionChainProvider.GetOptionContractList(self.ticker, self.context.Time)
            # Get the contracts
            contracts = self.optionChainProviderFilter(symbols, -self.strategy.nStrikesLeft, self.strategy.nStrikesRight, minDte, maxDte)

        # Stop the timer
        self.context.executionTimer.stop('Tools.DataHandler -> getOptionContracts')

        return contracts

    # Method to add option contracts data to the context.
    # @param contracts [Array]
    # @param resolution [Resolution]
    # @return [Symbol]
    def AddOptionContracts(self, contracts, resolution = Resolution.Minute):
        # Add this contract to the data subscription so we can retrieve the Bid/Ask price
        if self.__CashTicker():
            for contract in contracts:
                if contract.Symbol not in self.context.optionContractsSubscriptions:
                    self.context.AddIndexOptionContract(contract, resolution)
        else:
            for contract in contracts:
                if contract.Symbol not in self.context.optionContractsSubscriptions:
                    self.context.AddOptionContract(contract, resolution)

    # PRIVATE METHODS

    # Internal method to determine if we are using a cashticker to add the data.
    # @returns [Boolean]
    def __CashTicker(self):
        return self.ticker in self.CashIndices
