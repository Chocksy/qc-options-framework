#region imports
from AlgorithmImports import *
#endregion

from .Underlying import Underlying
from .ProviderOptionContract import ProviderOptionContract
import operator

class DataHandler:
    # The supported cash indices by QC https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/tickdata/us-cash-indices#05-Supported-Indices
    # These need to be added using AddIndex instead of AddEquity
    CashIndices = ['VIX','SPX','NDX']

    def __init__(self, context, ticker, strategy):
        self.ticker = ticker
        self.context = context
        self.strategy = strategy
        self.is_future_option = self.__FutureTicker()  # Flag to identify if we're dealing with future options

    # Method to add the ticker[String] data to the context.
    # @param resolution [Resolution]
    # @return [Symbol]
    def AddUnderlying(self, resolution=Resolution.Minute):
        if self.__CashTicker():
            return self.context.AddIndex(self.ticker, resolution=resolution)
        elif self.__FutureTicker():
            return self.context.AddFuture(self.ticker, resolution=resolution)
        else:
            return self.context.AddEquity(self.ticker, resolution=resolution)

    # SECTION BELOW IS FOR ADDING THE OPTION CHAIN
    # Method to add the option chain data to the context.
    # @param resolution [Resolution]
    def AddOptionsChain(self, underlying, resolution=Resolution.Minute):
        if self.ticker == "SPX":
            return self.context.AddIndexOption(underlying.Symbol, "SPXW", resolution)
        elif self.__CashTicker():
            return self.context.AddIndexOption(underlying.Symbol, resolution)
        elif self.is_future_option:
            return self.context.AddFutureOption(underlying.Symbol, self.FutureOptionFilterFunction)
        else:
            return self.context.AddOption(underlying.Symbol, resolution)

    # Should be called on an option object like this: option.SetFilter(self.OptionFilter)
    # !This method is called every minute if the algorithm resolution is set to minute
    def SetOptionFilter(self, underlying):
        self.context.executionTimer.start('Tools.DataHandler -> SetOptionFilter')
        self.context.logger.debug(f"SetOptionFilter -> underlying: {underlying}")

        if self.is_future_option:
            # For future options, we set the filter on the underlying future
            underlying.SetFilter(0, 182)  # Filter for futures expiring within the next 182 days
            # Add future options using AddOptionsChain
            self.AddOptionsChain(underlying, self.context.timeResolution)
            # Create canonical symbol for the mapped future contract
            self.strategy.optionSymbol = self.OptionsContract(underlying.Symbol)
        else:
            option = self.AddOptionsChain(underlying, self.context.timeResolution)
            option.SetFilter(self.OptionFilterFunction)
            self.strategy.optionSymbol = option.Symbol

        self.context.logger.debug(f"{self.__class__.__name__} -> SetOptionFilter -> Option Symbol: {self.strategy.optionSymbol}")
        self.context.executionTimer.stop('Tools.DataHandler -> SetOptionFilter')

    # SECTION BELOW HANDLES OPTION CHAIN PROVIDER METHODS
    def optionChainProviderFilter(self, symbols, min_strike_rank, max_strike_rank, minDte, maxDte):
        self.context.executionTimer.start('Tools.DataHandler -> optionChainProviderFilter')

        if len(symbols) == 0:
            self.context.logger.warning("No initial symbols provided to filter")
            return None

        self.context.logger.warning(f"Initial filter state: {len(symbols)} symbols, DTE range: {minDte}-{maxDte}")

        # Check minimum trade distance
        minimumTradeScheduleDistance = self.strategy.parameter("minimumTradeScheduleDistance", timedelta(hours=0))
        if (hasattr(self.context, 'lastOpenedDttm') and self.context.lastOpenedDttm is not None and 
            self.context.Time < (self.context.lastOpenedDttm + minimumTradeScheduleDistance)):
            return None

        # Filter by DTE first
        self.context.logger.warning(f"Filtering by DTE: {minDte}-{maxDte}")
        self.context.logger.warning(f"Current time: {self.context.Time.date()}")
        for symbol in symbols[:5]:  # Log first 5 symbols
            dte = (symbol.ID.Date.date() - self.context.Time.date()).days
            self.context.logger.warning(f"Symbol {symbol.ID.Symbol}: DTE={dte}, Strike={symbol.ID.StrikePrice}")

        filteredSymbols = [symbol for symbol in symbols
                          if minDte <= (symbol.ID.Date.date() - self.context.Time.date()).days <= maxDte]

        if not filteredSymbols:
            self.context.logger.warning(f"All {len(symbols)} symbols filtered out by DTE range {minDte}-{maxDte}")
            if len(symbols) > 0:
                available_dtes = sorted(set((symbol.ID.Date.date() - self.context.Time.date()).days for symbol in symbols))
                self.context.logger.warning(f"Available DTEs were: {available_dtes}")
            return None

        # Get unique expiry dates
        expiry_dates = sorted(set(symbol.ID.Date for symbol in filteredSymbols), reverse=True)
        
        # Handle dynamic DTE selection if enabled
        if (hasattr(self.strategy, 'dynamicDTESelection') and self.strategy.dynamicDTESelection and 
            hasattr(self.context, 'recentlyClosedDTE') and self.context.recentlyClosedDTE):
            valid_closed_trades = [
                trade for trade in self.context.recentlyClosedDTE 
                if trade["closeDte"] >= minDte
            ]
            if valid_closed_trades:
                last_closed_dte = valid_closed_trades[0]["closeDte"]
                # Find expiry date closest to last closed DTE
                target_expiry = min(expiry_dates, 
                                  key=lambda x: abs((x.date() - self.context.Time.date()).days - last_closed_dte))
                filteredSymbols = [s for s in filteredSymbols if s.ID.Date == target_expiry]
        else:
            # Use furthest/earliest expiry based on useFurthestExpiry
            selected_expiry = expiry_dates[0 if self.strategy.useFurthestExpiry else -1]
            filteredSymbols = [s for s in filteredSymbols if s.ID.Date == selected_expiry]

        # Filter based on allowMultipleEntriesPerExpiry
        if (hasattr(self.strategy, 'allowMultipleEntriesPerExpiry') and 
            not self.strategy.allowMultipleEntriesPerExpiry):
            open_expiries = set()
            for orderId in self.context.openPositions.values():
                position = self.context.allPositions[orderId]
                if position.strategyTag == self.strategy.nameTag:
                    open_expiries.add(position.expiryStr)
            
            filteredSymbols = [
                symbol for symbol in filteredSymbols 
                if symbol.ID.Date.strftime("%Y-%m-%d") not in open_expiries
            ]

        # Filter out non-tradable symbols for equities
        if not self.__CashTicker():
            before_tradable = len(filteredSymbols)
            tradable_symbols = []
            non_tradable_reasons = []

            for symbol in filteredSymbols[:5]:  # Sample first 5 symbols for detailed logging
                security = self.context.Securities[symbol.ID.Symbol]
                if security.IsTradable:
                    tradable_symbols.append(symbol)
                else:
                    non_tradable_reasons.append(f"Symbol {symbol.ID.Symbol}: IsTradable={security.IsTradable}")

            # If we found any tradable in the sample, use normal filtering
            if tradable_symbols:
                filteredSymbols = [x for x in filteredSymbols if self.context.Securities[x.ID.Symbol].IsTradable]
            else:
                # If none in sample were tradable, log reasons and try proceeding anyway
                self.context.logger.warning(f"Sample non-tradable reasons: {', '.join(non_tradable_reasons)}")
                self.context.logger.warning("Proceeding with all symbols despite tradability check")
                # Don't filter out non-tradable symbols
                tradable_symbols = filteredSymbols

            self.context.logger.warning(f"Tradability filter: {before_tradable} -> {len(filteredSymbols)} symbols")

        # Get underlying price
        underlying = Underlying(self.context, self.strategy.underlyingSymbol)
        underlyingLastPrice = underlying.Price()

        if underlyingLastPrice is None:
            self.context.logger.warning(f"No price available for {self.strategy.underlyingSymbol}")
            return None

        self.context.logger.warning(f"Underlying {self.strategy.underlyingSymbol} price: {underlyingLastPrice}")

        # Find ATM strike
        try:
            atm_strike = sorted(filteredSymbols, key=lambda x: abs(x.ID.StrikePrice - underlyingLastPrice))[0].ID.StrikePrice
            self.context.logger.warning(f"ATM strike found: {atm_strike} (Underlying: {underlyingLastPrice})")
        except IndexError:
            self.context.logger.warning("Unable to find ATM strike")
            return None

        # Get sorted strike list and find strike range
        strike_list = sorted(set([i.ID.StrikePrice for i in filteredSymbols]))
        atm_strike = sorted(filteredSymbols, key=lambda x: abs(x.ID.StrikePrice - underlyingLastPrice))[0].ID.StrikePrice
        
        self.context.logger.warning(f"Strike list: {strike_list}")
        self.context.logger.warning(f"ATM strike: {atm_strike}")
        
        # Find the index of the ATM strike
        atm_index = strike_list.index(atm_strike)
        
        # Calculate min and max indices, ensuring we don't go out of bounds
        min_index = max(0, atm_index + min_strike_rank)
        max_index = min(len(strike_list) - 1, atm_index + max_strike_rank)
        
        # Get the actual strike prices at these indices
        min_strike = strike_list[min_index]
        max_strike = strike_list[max_index]
        
        self.context.logger.warning(f"Strike range: {min_strike} - {max_strike}")

        # Filter by strike range (inclusive)
        selectedSymbols = [symbol for symbol in filteredSymbols
                                if min_strike <= symbol.ID.StrikePrice <= max_strike]

        self.context.logger.warning(f"Strike filter: {len(filteredSymbols)} -> {len(selectedSymbols)} symbols")

        # Convert to ProviderOptionContract objects
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

        if self.strategy.useSlice and slice is not None:
            if self.is_future_option:
                for continuous_future_symbol, futures_chain in slice.FuturesChains.items():
                    if continuous_future_symbol == self.strategy.underlyingSymbol:
                        for futures_contract in futures_chain:
                            canonical_fop_symbol = Symbol.CreateCanonicalOption(futures_contract.Symbol)
                            option_chain = slice.OptionChains.get(canonical_fop_symbol)
                            if option_chain is not None and option_chain.contracts.count != 0:
                                contracts = list(option_chain.Contracts.Values)
                                break
                        if contracts:
                            break
            else:
                for chain in slice.OptionChains:
                    if self.strategy.optionSymbol is None or chain.Key == self.strategy.optionSymbol:
                        if chain.Value.Contracts.Count != 0:
                            contracts = list(chain.Value)
                            break
            self.context.logger.debug(f"getOptionContracts -> number of contracts from slice: {len(contracts) if contracts else 0}")

        if contracts is None:
            if not self.is_future_option:
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
        for contract in contracts:
            if contract not in self.context.optionContractsSubscriptions:
                if self.is_future_option:
                    self.context.AddFutureOptionContract(contract, resolution)
                elif self.__CashTicker():
                    self.context.AddIndexOptionContract(contract, resolution)
                else:
                    self.context.AddOptionContract(contract, resolution)
                self.context.optionContractsSubscriptions.append(contract)
                # Calculate Greeks after adding the contract
                self._initializeGreeks(self.context.Securities[contract])

    def OptionsContract(self, underlyingSymbol):
        if self.ticker == "SPX":
            return Symbol.create_canonical_option(underlyingSymbol, "SPXW", Market.USA, "?SPXW")
        elif self.is_future_option:
            return Symbol.create_canonical_option(underlyingSymbol)
        else:
            return Symbol.create_canonical_option(underlyingSymbol, Market.USA, f"?{self.ticker}")

    # PRIVATE METHODS

    def __FutureTicker(self):
        # Implement logic to determine if the ticker is a future
        return self.ticker in [Futures.Indices.SP_500_E_MINI]

    # Internal method to determine if we are using a cashticker to add the data.
    # @returns [Boolean]
    def __CashTicker(self):
        return self.ticker in self.CashIndices

    def OptionFilterFunction(self, universe):
        return universe.Strikes(-self.strategy.nStrikesLeft, self.strategy.nStrikesRight) \
                       .Expiration(max(0, self.strategy.dte - self.strategy.dteWindow), max(0, self.strategy.dte)) \
                       .IncludeWeeklys()

    def FutureOptionFilterFunction(self, universe):
        return (universe
                .IncludeWeeklys()
                .Strikes(-self.strategy.nStrikesLeft, self.strategy.nStrikesRight)
                .Expiration(max(0, self.strategy.dte - self.strategy.dteWindow), max(0, self.strategy.dte)))

    def _initializeGreeks(self, security):
        """Initialize Greeks for an option contract after it's been added"""
        try:
            if security.Type in [SecurityType.Option, SecurityType.IndexOption]:
                right = OptionRight.CALL if security.symbol.ID.option_right == OptionRight.PUT else OptionRight.PUT
                mirror_symbol = Symbol.create_option(
                    security.symbol.ID.underlying.symbol,
                    security.symbol.ID.market,
                    security.symbol.ID.option_style,
                    right,
                    security.symbol.ID.strike_price,
                    security.symbol.ID.date
                )

                security.iv = self.context.iv(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.delta = self.context.d(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.gamma = self.context.g(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.vega = self.context.v(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.rho = self.context.r(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
                security.theta = self.context.t(security.symbol, mirror_symbol, resolution=self.context.timeResolution)
        except Exception as e:
            self.context.logger.warning(f"Greeks Initialization: Data not available: {e}")