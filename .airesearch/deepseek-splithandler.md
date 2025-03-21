# Final Implementation Structure (Revised and Enhanced)

This document outlines the enhanced architecture and filtering approach for our quantitative options trading system. It improves upon the previous implementation by integrating dynamic universe support, merging default filters with strategy-specific lambdas, and providing clear distinctions between equity/index options and future options. The expanded filtering methods within the DataHandler class provide comprehensive capabilities while maintaining backward compatibility with existing strategies.

---

## 1. Core Files and Directory Structure

```
DataHandler/
├── DataHandler.py          # Main data subscription & filtering logic
├── __init__.py             # Package exports
└── Services/
    ├── UniverseHandler.py  # Dynamic universe selection
    └── OptionChainProviderService.py  # Option chain filtering fallback
```

---

## 2. DataHandler.py Key Methods

```python
class DataHandler:
    def __init__(self, context, ticker, strategy):
        self.context = context
        self.ticker = ticker
        self.strategy = strategy
        # Initialize the universe handler
        self.universe_handler = UniverseHandler(context, strategy)
        # Define supported cash indices
        self.CashIndices = ['VIX', 'SPX', 'NDX']
        # Flag to identify if dealing with future options
        self.is_future_option = self.__FutureTicker()
        # Initialize the OptionChainProviderService
        self.context.OptionChainProviderService = OptionChainProviderService(self.context)

    def AddUnderlying(self, resolution=Resolution.Minute):
        """
        Adds a single underlying asset based on its type (equity, index, or future).
        Returns the added security object.
        
        Args:
            resolution: The data resolution to use (default: Minute)
            
        Returns:
            The underlying security object
        """
        if self.__CashTicker():
            return self.context.AddIndex(self.ticker, resolution=resolution)
        elif self.__FutureTicker():
            return self.context.AddFuture(self.ticker, resolution=resolution)
        else:
            return self.context.AddEquity(self.ticker, resolution=resolution)

    def AddUniverse(self, resolution=Resolution.Minute):
        """
        Uses dynamic universe selection via UniverseHandler.
        The strategy must define a universeFilter lambda that accepts fundamentals and returns eligible symbols.
        
        Args:
            resolution: The data resolution to use (default: Minute)
            
        Returns:
            The underlying security object from the selected universe
        """
        # Delegate to the universe handler to create a screened universe
        underlying = self.universe_handler.add_screened_universe(
            self.strategy.universeFilter,  # The filtering lambda provided by the strategy
            self.OptionFilterFunction,     # The default option filter function
            resolution
        )
        return underlying

    def AddOptionsChain(self, underlying, resolution=Resolution.Minute, filter_func=None):
        """
        Routes to the appropriate QC function based on asset type to add an options chain.
        
        Args:
            underlying: The underlying security
            resolution: The data resolution to use (default: Minute)
            filter_func: Optional custom filter function
            
        Returns:
            The option chain object
        """
        if self.ticker == "SPX":
            # Special case for SPX to use SPXW (weekly) options
            return self.context.AddIndexOption(underlying.Symbol, "SPXW", resolution)
        elif self.__CashTicker():
            # Other cash indices
            return self.context.AddIndexOption(underlying.Symbol, resolution)
        elif self.is_future_option:
            # For future options, use provided filter or default
            return self.context.AddFutureOption(
                underlying.Symbol, 
                filter_func if filter_func is not None else self.OptionFilterFunction
            )
        else:
            # Regular equity options
            return self.context.AddOption(underlying.Symbol, resolution)

    def SetOptionFilter(self, underlying):
        """
        Sets up option chain filters for the underlying asset.
        Handles both regular options and future options differently.
        
        Args:
            underlying: The underlying security
        """
        self.context.executionTimer.start('DataHandler -> SetOptionFilter')
        self.context.logger.debug(f"SetOptionFilter -> underlying: {underlying}")

        if self.is_future_option:
            # For futures, first set filter on the future itself
            underlying.SetFilter(0, 90)  # Filter futures expiring within 90 days
            
            # Add the options chain with the filter
            future_option = self.AddOptionsChain(underlying, self.context.timeResolution, self.OptionFilterFunction)
            # Store the canonical option symbol for reference
            self.strategy.optionSymbol = self.OptionsContract(underlying.Symbol)
        else:
            # Add options chain and set the filter
            option = self.AddOptionsChain(underlying, self.context.timeResolution)
            # Merge the default filter with the strategy-specific filter (if provided)
            merged_filter = self.MergeOptionFilters(
                self.OptionFilterFunction,
                getattr(self.strategy, "optionFilterLambda", None)
            )
            option.SetFilter(merged_filter)
            self.strategy.optionSymbol = option.Symbol

        self.context.logger.debug(f"DataHandler -> SetOptionFilter -> Option Symbol: {self.strategy.optionSymbol}")
        self.context.executionTimer.stop('DataHandler -> SetOptionFilter')

    def MergeOptionFilters(self, default_filter, extra_filter=None):
        """
        Merges a default filter with an optional extra filter.
        If extra_filter is provided, it's applied after the default_filter.
        
        Args:
            default_filter: The default filtering function
            extra_filter: An optional additional filter to apply
            
        Returns:
            A merged filter function
        """
        if extra_filter and callable(extra_filter):
            return lambda universe: extra_filter(default_filter(universe))
        return default_filter

    def getOptionContracts(self, slice=None):
        """
        Retrieves option contracts from slice data or falls back to provider.
        
        Args:
            slice: Current data slice (optional)
            
        Returns:
            List of option contracts matching the filter criteria
        """
        self.context.executionTimer.start('DataHandler -> getOptionContracts')
        contracts = None
        
        # Define DTE filtering range
        minDte = max(0, self.strategy.dte - self.strategy.dteWindow)
        maxDte = max(0, self.strategy.dte)

        # Try to get contracts from slice data
        if self.strategy.useSlice and slice is not None:
            if self.is_future_option:
                # Logic for getting future option contracts from slice
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
                # Logic for getting equity/index option contracts from slice
                for chain in slice.OptionChains:
                    if self.strategy.optionSymbol is None or chain.Key == self.strategy.optionSymbol:
                        if chain.Value.Contracts.Count != 0:
                            contracts = list(chain.Value)
                            break

        # Fallback: use OptionChainProviderService if no contracts found in slice
        if contracts is None:
            if not self.is_future_option:
                # Get the canonical option symbol
                canonical_symbol = self.OptionsContract(self.strategy.underlyingSymbol)
                # Fetch raw contract list
                symbols = self.context.OptionChainProvider.GetOptionContractList(canonical_symbol, self.context.Time)
                # Get the underlying price
                underlying_price = self.context.Securities[self.strategy.underlyingSymbol].Price
                # Apply filtering with OptionChainProviderService
                contracts = self.context.OptionChainProviderService.optionChainProviderFilter(
                    symbols,
                    -self.strategy.nStrikesLeft,
                    self.strategy.nStrikesRight,
                    minDte,
                    maxDte,
                    underlying_price
                )
            else:
                self.context.logger.debug("Fallback contract retrieval not implemented for future options")
        
        self.context.executionTimer.stop('DataHandler -> getOptionContracts')
        return contracts

    def OptionFilterFunction(self, universe):
        """
        Default filter for equity/index options.
        
        Args:
            universe: Option chain universe to filter
            
        Returns:
            Filtered universe
        """
        # Apply strike range, expiration, and include weeklys
        return universe.Strikes(-self.strategy.nStrikesLeft, self.strategy.nStrikesRight) \
                      .Expiration(max(0, self.strategy.dte - self.strategy.dteWindow), max(0, self.strategy.dte)) \
                      .IncludeWeeklys()

    def __FutureTicker(self):
        """
        Internal method to determine if the ticker is a future.
        
        Returns:
            Boolean indicating if ticker is a future
        """
        return self.ticker in [Futures.Indices.SP_500_E_MINI]

    def __CashTicker(self):
        """
        Internal method to determine if the ticker is a cash index.
        
        Returns:
            Boolean indicating if ticker is a cash index
        """
        return self.ticker in self.CashIndices
        
    def OptionsContract(self, underlyingSymbol):
        """
        Creates a canonical option symbol for the underlying.
        
        Args:
            underlyingSymbol: The underlying security symbol
            
        Returns:
            The canonical option symbol
        """
        return Symbol.CreateOption(underlyingSymbol, Market.USA, OptionStyle.American, OptionRight.Call, 0, datetime.max)
```

---

## 3. UniverseHandler.py Implementation

```python
class UniverseHandler:
    def __init__(self, context, strategy):
        """
        Initialize the UniverseHandler with context and strategy.
        
        Args:
            context: The algorithm context
            strategy: The trading strategy
        """
        self.context = context
        self.strategy = strategy

    def add_screened_universe(self, equity_filter, option_filter, resolution=Resolution.Minute):
        """
        Applies the given equity_filter to fundamentals and sets up a dynamic universe.
        
        Args:
            equity_filter: A lambda function for filtering equities based on fundamentals
            option_filter: The option filter to apply to selected equities
            resolution: Data resolution (default: Minute)
            
        Returns:
            The first underlying security that passes the filter
        """
        if not callable(equity_filter):
            self.context.logger.error("Universe filter must be a callable function")
            return None
            
        def universe_selection(fundamental):
            """
            Applies the strategy's filter to select symbols from fundamentals.
            """
            return equity_filter(fundamental)

        # Register the universe selection with QuantConnect
        self.context.AddUniverse(universe_selection)

        # In a complete implementation, we would handle multiple symbols
        # For now, we select the first symbol that passes the filter
        selected_symbols = []
        
        # Wait for fundamentals to be ready
        if hasattr(self.context, 'FundamentalUniverse') and self.context.FundamentalUniverse:
            selected_symbols = [fund.Symbol for fund in self.context.FundamentalUniverse 
                               if universe_selection(fund)]
                               
        if selected_symbols:
            # Add the first selected equity and return it
            underlying = self.context.AddEquity(selected_symbols[0], resolution=resolution)
            return underlying
        else:
            self.context.logger.error("No symbols passed the universe filter")
            return None
```

---

## 4. OptionChainProviderService.py Implementation

```python
class OptionChainProviderService:
    def __init__(self, context):
        """
        Initialize the service with the algorithm context.
        
        Args:
            context: The algorithm context
        """
        self.context = context

    def optionChainProviderFilter(self, symbols, min_strike_rank, max_strike_rank, minDte, maxDte, underlying_price):
        """
        Filters raw option contract symbols from the OptionChainProvider.
        
        Args:
            symbols: List of raw option contract symbols
            min_strike_rank: Lower relative rank from the ATM strike
            max_strike_rank: Upper relative rank from the ATM strike
            minDte: Minimum days-to-expiration
            maxDte: Maximum days-to-expiration
            underlying_price: Price of the underlying asset
            
        Returns:
            List of filtered option contracts
        """
        self.context.logger.debug(f"Filtering {len(symbols)} symbols with strike ranks {min_strike_rank}:{max_strike_rank}, DTE {minDte}:{maxDte}")
        
        # Initialize empty result list
        filtered = []
        current_time = self.context.Time
        
        # Step 1: Filter by DTE
        dte_filtered = []
        for sym in symbols:
            dte = (sym.ID.Date - current_time.date()).days
            if minDte <= dte <= maxDte:
                dte_filtered.append(sym)
                
        self.context.logger.debug(f"DTE filter: {len(symbols)} -> {len(dte_filtered)} symbols")
        
        if not dte_filtered:
            return filtered
            
        # Step 2: Find ATM strike
        atm_strike = None
        min_distance = float('inf')
        
        for sym in dte_filtered:
            distance = abs(sym.ID.Strike - underlying_price)
            if distance < min_distance:
                min_distance = distance
                atm_strike = sym.ID.Strike
                
        if atm_strike is None:
            self.context.logger.warning("Could not determine ATM strike")
            return filtered
            
        self.context.logger.debug(f"ATM strike found: {atm_strike} (Underlying: {underlying_price})")
        
        # Step 3: Get sorted strikes and determine strike range
        strike_list = sorted(set(sym.ID.Strike for sym in dte_filtered))
        
        try:
            atm_strike_idx = strike_list.index(atm_strike)
            min_strike_idx = max(0, atm_strike_idx + min_strike_rank)
            max_strike_idx = min(len(strike_list) - 1, atm_strike_idx + max_strike_rank)
            
            min_strike = strike_list[min_strike_idx]
            max_strike = strike_list[max_strike_idx]
            
            self.context.logger.debug(f"Strike range: {min_strike} to {max_strike}")
        except ValueError:
            self.context.logger.warning(f"ATM strike {atm_strike} not found in strike list")
            return filtered
            
        # Step 4: Filter by strike range
        for sym in dte_filtered:
            if min_strike <= sym.ID.Strike <= max_strike:
                # Subscribe to the contract data
                if self.context.Securities.ContainsKey(sym):
                    # Create option contract object
                    contract = ProviderOptionContract(sym, underlying_price, self.context)
                    filtered.append(contract)
                else:
                    # Add contract to subscriptions
                    if self.__isCashSymbol(sym.Underlying):
                        self.context.AddIndexOptionContract(sym, Resolution.Minute)
                    else:
                        self.context.AddOptionContract(sym, Resolution.Minute)
                    # Create and store contract
                    contract = ProviderOptionContract(sym, underlying_price, self.context)
                    filtered.append(contract)
                    
        self.context.logger.debug(f"Final filter result: {len(filtered)} contracts")
        return filtered
        
    def __isCashSymbol(self, symbol):
        """
        Determines if a symbol is a cash index.
        
        Args:
            symbol: The symbol to check
            
        Returns:
            Boolean indicating if the symbol is a cash index
        """
        cash_indices = ['VIX', 'SPX', 'NDX']
        return symbol.Value in cash_indices
```

---

## 5. SetupBaseStructure Integration

```python
class SetupBaseStructure:
    def AddUnderlying(self, strategy, ticker=None, universe_filter=None, option_filter=None):
        """
        Adds an underlying asset and its associated options chain.
        If a universe_filter is provided, dynamic universe selection is used.
        
        Args:
            strategy: The trading strategy
            ticker: Optional ticker symbol (required for single asset, optional for universe)
            universe_filter: Optional lambda for dynamic universe selection
            option_filter: Optional filter lambda for option chains (equity, index, or future options)
            
        Returns:
            Self for method chaining
        """
        self.context.strategies.append(strategy)
        
        # Set option filter if provided
        if option_filter is not None:
            strategy.optionFilterLambda = option_filter
        
        # Handle dynamic universe selection
        if universe_filter:
            # If using universe filtering without an explicit ticker, provide a placeholder
            if not ticker:
                ticker = "DYNAMIC"
            strategy.ticker = ticker
            strategy.universeFilter = universe_filter
            
            # Initialize DataHandler
            strategy.dataHandler = DataHandler(self.context, ticker, strategy)
            
            # Use dynamic universe selection
            underlying = strategy.dataHandler.AddUniverse(self.context.timeResolution)
        else:
            # Single asset mode
            strategy.ticker = ticker
            strategy.dataHandler = DataHandler(self.context, ticker, strategy)
            underlying = strategy.dataHandler.AddUnderlying(self.context.timeResolution)

        # Configure the underlying
        if underlying:
            underlying.SetDataNormalizationMode(DataNormalizationMode.Raw)
            strategy.underlyingSymbol = underlying.Symbol

            # Set up option chain if requested
            if getattr(strategy, 'useSlice', False):
                strategy.dataHandler.SetOptionFilter(underlying)

            # Set benchmark and schedule market open event
            self.context.SetBenchmark(underlying.Symbol)
            self.context.Schedule.On(
                self.context.DateRules.EveryDay(strategy.underlyingSymbol),
                self.context.TimeRules.AfterMarketOpen(strategy.underlyingSymbol, minutesAfterOpen=1),
                self.MarketOpenStructure
            )
        else:
            self.context.logger.error(f"Failed to add underlying for strategy {strategy.__class__.__name__}")
            
        return self
```

---

## 6. Main Algorithm Integration

No additional initialization required in the main algorithm as the OptionChainProviderService is now initialized within the DataHandler class.

---

## 7. Usage Examples

### Equity Options Example (Alpha Model)

```python
class ExampleEquityAlphaModel(Base):
    # Override default parameters with strategy-specific ones
    PARAMETERS = {
        "useSlice": True,
        "dte": 35,
        "dteWindow": 5,
        "nStrikesLeft": 2,
        "nStrikesRight": 2
    }

    def __init__(self, context):
        super().__init__(context)
        self.name = "ExampleEquityAlpha"
        self.nameTag = "EquityOptions"
        self.ticker = "AAPL"
        
        # Pass the option filter lambda directly
        option_filter = lambda u: u.Delta(0.3, 0.7)
        self.context.structure.AddUnderlying(self, self.ticker, option_filter=option_filter)
```

### Index Options Example

```python
class ExampleIndexAlphaModel(Base):
    PARAMETERS = {
        "useSlice": True,
        "dte": 60,
        "dteWindow": 0,
        "nStrikesLeft": 1,
        "nStrikesRight": 1
    }
    
    def __init__(self, context):
        super().__init__(context)
        self.name = "ExampleIndexAlpha"
        self.nameTag = "SPXOptions"
        self.ticker = "SPX"
        
        # Pass the IV filter lambda directly
        iv_filter = lambda u: u.IV(0, 25)
        self.context.structure.AddUnderlying(self, self.ticker, option_filter=iv_filter)
```

### Future Options Example

```python
class ExampleFutureOptionAlphaModel(Base):
    PARAMETERS = {
        "useSlice": True,
        "dte": 90,
        "dteWindow": 0,
        "nStrikesLeft": 1,
        "nStrikesRight": 1
    }

    def __init__(self, context):
        super().__init__(context)
        self.name = "ExampleFutureOptionAlpha"
        self.nameTag = "ESOptions"
        self.ticker = Futures.Indices.SP_500_E_MINI
        
        # Pass the future option filter lambda directly
        future_filter = lambda u: u.CallsOnly().Strikes(-1, 1).Expiration(0, 90)
        self.context.structure.AddUnderlying(
            self, 
            self.ticker,
            option_filter=future_filter
        )
```

### Dynamic Universe Example

```python
class MarketCapCallOptionAlphaModel(Base):
    PARAMETERS = {
        "useSlice": True,
        "dte": 7,
        "dteWindow": 0,
        "nStrikesLeft": 2,
        "nStrikesRight": 2
    }

    def __init__(self, context):
        super().__init__(context)
        self.name = "MarketCapCallOption"
        self.nameTag = "DynamicCallOptions"
        
        # Define universe selection criteria
        universe_filter = lambda fundamentals: [
            f.Symbol for f in fundamentals 
            if hasattr(f, 'MarketCapitalization') and f.MarketCapitalization > 10e9
        ]
        
        # Define option filter criteria
        option_filter = lambda u: u.CallsOnly().Delta(0.10, 0.30).Expiration(0, 7)
        
        # Use dynamic selection with explicit filters
        self.context.structure.AddUnderlying(
            self, 
            ticker=None, 
            universe_filter=universe_filter,
            option_filter=option_filter
        )
```

---

## 8. Implementation Steps and Migration Plan

To implement this architecture, follow these steps:

1. **Create Services Directory Structure**
   ```
   mkdir -p DataHandler/Services
   touch DataHandler/Services/__init__.py
   ```

2. **Implement Core Components**
   - Create `UniverseHandler.py` in the Services directory
   - Create `OptionChainProviderService.py` in the Services directory
   - Modify `DataHandler.py` to include the new functionality

3. **Update SetupBaseStructure**
   - Modify the `AddUnderlying` method to support universe filters

4. **Test and Migrate Existing Strategies**
   - Test with simple equity option strategies first
   - Gradually migrate index option strategies
   - Finally, test and migrate future option strategies

5. **Documentation Updates**
   - Update strategy documentation to include universe selection examples
   - Create reference documentation for the new filter functions

---

## 9. Additional Considerations

1. **Error Handling**
   - Both `UniverseHandler` and `OptionChainProviderService` should include proper error logging
   - Consider implementing retry logic for option chain retrieval

2. **Performance Optimization**
   - Cache frequently accessed data like ATM strike calculations
   - Consider implementing contract caching to reduce duplicate requests

3. **Extensibility**
   - The architecture should allow for easy addition of new asset types
   - Consider creating a base service class for shared functionality

4. **Testing**
   - Implement unit tests for each component
   - Create integration tests for the complete workflow

This revised architecture provides a comprehensive solution for handling both single-asset and dynamic universe-based options trading strategies while maintaining backward compatibility.

