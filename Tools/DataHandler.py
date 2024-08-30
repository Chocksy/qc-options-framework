#region imports
from AlgorithmImports import *
#endregion

from .Underlying import Underlying
from .ProviderOptionContract import ProviderOptionContract
from .PositionSerializer import PositionSerializer
import operator

class DataHandler:
    # The supported cash indices by QC https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/tickdata/us-cash-indices#05-Supported-Indices
    # These need to be added using AddIndex instead of AddEquity
    CashIndices = ['VIX','SPX','NDX']

    def __init__(self, context, ticker, strategy):
        self.ticker = ticker
        self.context = context
        self.strategy = strategy
        position_serializer = PositionSerializer(context)
        self.last_run_symbols = position_serializer.get_option_symbols_from_positions()

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
        self.context.logger.debug(f"optionChainProviderFilter -> symbols count: {len(symbols)}")
        
        if len(symbols) == 0:
            self.context.logger.warning("No symbols provided to optionChainProviderFilter")
            return None

        # filtering the symbols in minDte,maxDte and if anything stored from the last run 
        filteredSymbols = [symbol for symbol in symbols
                            if (minDte <= (symbol.ID.Date.date() - self.context.Time.date()).days <= maxDte) or (str(symbol.value) in self.last_run_symbols)]

        self.context.logger.debug(f"Filtered symbols count: {len(filteredSymbols)}")
        self.context.logger.debug(f"Context Time: {self.context.Time.date()}")
        unique_dates = set(symbol.ID.Date.date() for symbol in symbols)
        self.context.logger.debug(f"Unique symbol dates: {unique_dates}")
        self.context.logger.debug(f"optionChainProviderFilter -> filteredSymbols: {filteredSymbols}")
        
        if not filteredSymbols:
            self.context.logger.warning("No symbols left after date filtering")
            return None

        if not self.__CashTicker():
            filteredSymbols = [x for x in filteredSymbols if self.context.Securities[x.ID.Symbol].IsTradable]
            self.context.logger.debug(f"Tradable filtered symbols count: {len(filteredSymbols)}")

        if not filteredSymbols:
            self.context.logger.warning("No tradable symbols left after filtering")
            return None

        underlying = Underlying(self.context, self.strategy.underlyingSymbol)
        underlyingLastPrice = underlying.Price()

        self.context.logger.debug(f"Underlying last price: {underlyingLastPrice}")

        if underlyingLastPrice is None:
            self.context.logger.warning("Underlying price is None")
            return None

        try:
            atm_strike = sorted(filteredSymbols, key=lambda x: abs(x.ID.StrikePrice - underlyingLastPrice))[0].ID.StrikePrice
        except IndexError:
            self.context.logger.error("Unable to find ATM strike. Check if filteredSymbols is empty or if strike prices are available.")
            return None

        self.context.logger.debug(f"ATM strike: {atm_strike}")

        strike_list = sorted(set([i.ID.StrikePrice for i in filteredSymbols]))
        atm_strike_rank = strike_list.index(atm_strike)
        min_strike = strike_list[max(0, atm_strike_rank + min_strike_rank + 1)]
        max_strike = strike_list[min(atm_strike_rank + max_strike_rank - 1, len(strike_list)-1)]

        selectedSymbols = [symbol for symbol in filteredSymbols
                                if min_strike <= symbol.ID.StrikePrice <= max_strike]
        
        self.context.logger.debug(f"Selected symbols count: {len(selectedSymbols)}")

        contracts = []
        for symbol in selectedSymbols:
            self.AddOptionContracts([symbol], resolution=self.context.timeResolution)
            contract = ProviderOptionContract(symbol, underlyingLastPrice, self.context)
            contracts.append(contract)

        self.context.executionTimer.stop('Tools.DataHandler -> optionChainProviderFilter')

        return contracts

    def getOptionContracts(self, slice=None):
        self.context.executionTimer.start('Tools.DataHandler -> getOptionContracts')

        contracts = None
        minDte = max(0, self.strategy.dte - self.strategy.dteWindow)
        maxDte = max(0, self.strategy.dte)
        self.context.logger.debug(f"getOptionContracts -> minDte: {minDte}")
        self.context.logger.debug(f"getOptionContracts -> maxDte: {maxDte}")

        if self.strategy.useSlice:
            for chain in slice.OptionChains:
                if self.strategy.optionSymbol == None or chain.Key != self.strategy.optionSymbol:
                    continue
                if chain.Value.Contracts.Count != 0:
                    contracts = [
                        contract for contract in chain.Value if minDte <= (contract.Expiry.date() - self.context.Time.date()).days <= maxDte
                    ]
            self.context.logger.debug(f"getOptionContracts -> number of contracts from slice: {len(contracts) if contracts else 0}")

        if contracts is None:
            canonical_symbol = self.OptionsContract(self.strategy.underlyingSymbol)
            symbols = self.context.OptionChainProvider.GetOptionContractList(canonical_symbol, self.context.Time)
            contracts = self.optionChainProviderFilter(symbols, -self.strategy.nStrikesLeft, self.strategy.nStrikesRight, minDte, maxDte)

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
                if contract not in self.context.optionContractsSubscriptions:
                    self.context.AddIndexOptionContract(contract, resolution)
                    self.context.optionContractsSubscriptions.append(contract)
        else:
            for contract in contracts:
                if contract not in self.context.optionContractsSubscriptions:
                    self.context.AddOptionContract(contract, resolution)
                    self.context.optionContractsSubscriptions.append(contract)

    def OptionsContract(self, underlyingSymbol):
        if self.ticker == "SPX":
            return Symbol.create_canonical_option(underlyingSymbol, "SPXW", Market.USA, "?SPXW")
        else:
            return Symbol.create_canonical_option(underlyingSymbol, Market.USA, f"?{self.ticker}")
            

    # PRIVATE METHODS

    # Internal method to determine if we are using a cashticker to add the data.
    # @returns [Boolean]
    def __CashTicker(self):
        return self.ticker in self.CashIndices

