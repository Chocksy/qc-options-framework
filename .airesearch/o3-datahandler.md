Below is a technical specification that details our agreed improvements and outlines the steps needed to enhance your DataHandler (and related components) using recent QuantConnect features.

---

## 1. Overview

The goal is to modernize the data and option chain handling in the algorithm by leveraging new QuantConnect features. This includes:
- Using built-in universe selection methods for options filtering.
- Improving data filtering and tradability checks.
- Refactoring Greek calculations to use native pricing models.
- Streamlining the security initialization and subscription process.

---

## 2. Goals & Objectives

- **Simplify Option Chain Management:**  
  Replace manual filtering (in `SetOptionFilter` and `optionChainProviderFilter`) with QuantConnect’s native universe selection (e.g. `OptionUniverseSelectionModel`).

- **Improve Data Consistency & Efficiency:**  
  Use built-in flags such as `IsTradable` to reduce redundant checks and ensure that data subscriptions are correctly managed.

- **Native Greek Calculations:**  
  Replace manual Greek calls with native models or built-in configuration options, reducing the risk of errors and simplifying maintenance.

- **Standardize Security Setup:**  
  Refine the security initializer to use modern risk models, new brokerage options, and leaner code.

---

## 3. Proposed Changes

### 3.1 DataHandler Enhancements

1. **Replace Manual Option Filtering with Universe Selection:**

   - **Current:**  
     The code manually calls `option.SetFilter(self.OptionFilterFunction)` and processes slices to retrieve contracts.

   - **New Approach:**  
     Use QuantConnect’s `OptionUniverseSelectionModel` to subscribe and filter contracts based on parameters like strikes and expiration.

   - **Example Code:**

   ```python
   # Replace SetOptionFilter with Universe-based selection
   def SetOptionFilter(self, underlying):
       self.context.executionTimer.start('Tools.DataHandler -> SetOptionFilter')
       self.context.logger.debug(f"SetOptionFilter -> underlying: {underlying}")

       if self.is_future_option:
           underlying.SetFilter(0, 182)  # Filtering future options remains similar
           self.AddOptionsChain(underlying, self.context.timeResolution)
           self.strategy.optionSymbol = self.OptionsContract(underlying.Symbol)
       else:
           # Leverage QuantConnect's OptionUniverseSelectionModel for a cleaner subscription.
           option_universe = OptionUniverseSelectionModel(
               underlying.Symbol,
               lambda universe: universe.IncludeWeeklys()
                                     .Strikes(-self.strategy.nStrikesLeft, self.strategy.nStrikesRight)
                                     .Expiration(max(0, self.strategy.dte - self.strategy.dteWindow), max(0, self.strategy.dte))
           )
           # Attach the universe model to the algorithm (or use it in the AddUniverse call)
           self.context.AddUniverseSelection(option_universe)
           # The resulting option symbol is managed by QC
           self.strategy.optionSymbol = option_universe.CanonicalSymbol

       self.context.logger.debug(f"{self.__class__.__name__} -> SetOptionFilter -> Option Symbol: {self.strategy.optionSymbol}")
       self.context.executionTimer.stop('Tools.DataHandler -> SetOptionFilter')
   ```

2. **Improve Tradability Filtering:**

   - **Current:**  
     Manual filtering in `optionChainProviderFilter` where contracts are first sliced by DTE and then checked.

   - **Proposed:**  
     Use list comprehensions with the native `IsTradable` flag. This removes the need to sample or filter later.

   - **Example Code:**

   ```python
   def optionChainProviderFilter(self, symbols, min_strike_rank, max_strike_rank, minDte, maxDte):
       self.context.executionTimer.start('Tools.DataHandler -> optionChainProviderFilter')

       if not symbols:
           self.context.logger.warning("No initial symbols provided to filter")
           return None

       self.context.logger.warning(f"Initial filter state: {len(symbols)} symbols, DTE range: {minDte}-{maxDte}")

       # Filter using the DTE range and native IsTradable flag
       filtered = [s for s in symbols if 
                   minDte <= (s.ID.Date.date() - self.context.Time.date()).days <= maxDte and 
                   self.context.Securities[s].IsTradable]

       if not filtered:
           self.context.logger.warning(f"All {len(symbols)} symbols filtered out by DTE range {minDte}-{maxDte}")
           self.context.executionTimer.stop('Tools.DataHandler -> optionChainProviderFilter')
           return None

       # Determine contracts using sorted expiry dates
       expiry_dates = sorted(set(s.ID.Date for s in filtered), reverse=True)
       # Add additional dynamic DTE logic as needed ...

       self.context.executionTimer.stop('Tools.DataHandler -> optionChainProviderFilter')
       return filtered
   ```

3. **Refactor Greek Calculations:**

   - **Current:**  
     Manual calls to `self.context.iv`, `self.context.d`, etc.

   - **Proposed:**  
     Use QuantConnect's native option Greek model or set up a dedicated greek model via `SetOptionGreekModel`.

   - **Example Code:**

   ```python
   def _initializeGreeks(self, security):
       """Assign built-in greek calculations using the default model."""
       try:
           if security.Type in [SecurityType.Option, SecurityType.IndexOption]:
               # Use a dedicated greek calculation model
               security.SetOptionGreekModel(DefaultOptionGreekModel())
       except Exception as e:
           self.context.logger.warning(f"Greeks Initialization Error: {e}")
   ```

### 3.2 SetupBaseStructure Adjustments

1. **Modernize Security Initializer:**

   - **Update Brokerage & Security Settings:**  
     In `CompleteSecurityInitializer`, refine initialization to use new models when available:
     
     - Use `SetOptionGreekModel` for options rather than manual Greek updates.
     - Configure fill, fee, and price models with updated pricing functions.

   - **Example Code Changes:**

   ```python
   def CompleteSecurityInitializer(self, security: Security) -> None:
       self.context.logger.debug(f"{self.__class__.__name__} -> CompleteSecurityInitializer -> Security: {security}")
       security.set_buying_power_model(BuyingPowerModel.NULL)

       if self.context.LiveMode:
           return

       self.context.executionTimer.start()
       security.SetDataNormalizationMode(DataNormalizationMode.Raw)
       security.SetMarketPrice(self.context.GetLastKnownPrice(security))

       if security.Type == SecurityType.Equity:
           security.VolatilityModel = StandardDeviationOfReturnsVolatilityModel(30)
           history = self.context.History(security.Symbol, 31, Resolution.Daily)
           if not history.empty and 'close' in history.columns:
               for time, row in history.loc[security.Symbol].iterrows():
                   trade_bar = TradeBar(time, security.Symbol, row.open, row.high, row.low, row.close, row.volume)
                   security.VolatilityModel.Update(security, trade_bar)
       elif security.Type == SecurityType.FutureOption:
           security.SetFillModel(BetaFillModel(self.context))
           security.SetFeeModel(TastyWorksFeeModel())
           security.PriceModel = OptionPriceModels.CrankNicolsonFD()
           security.SetOptionAssignmentModel(NullOptionAssignmentModel())
           try:
               security.SetOptionGreekModel(DefaultOptionGreekModel())
           except Exception as e:
               self.context.logger.warning(f"FutureOption Init: Data not available ({e})")
       elif security.Type in [SecurityType.Option, SecurityType.IndexOption]:
           security.SetFillModel(BetaFillModel(self.context))
           security.SetFeeModel(TastyWorksFeeModel())
           security.PriceModel = OptionPriceModels.CrankNicolsonFD()
           if security.Type == SecurityType.IndexOption:
               security.SetOptionAssignmentModel(NullOptionAssignmentModel())
           security.SetOptionGreekModel(DefaultOptionGreekModel())
       
       self.context.executionTimer.stop()
   ```

2. **Streamline Data Subscriptions:**

   - Keep the subscription dictionaries (`optionContractsSubscriptions`, etc.) but key off modern QC APIs where possible.
   - Replace manual removal or lifecycle management code with improved logic (e.g., using the QC-managed subscription system).

### 3.3 Portfolio Construction Update

1. **Use an Equal Weighting or Risk-Based Approach:**

   - Replace custom portfolio construction if possible with a refined implementation such as:

   ```python
   class OptionsPortfolioConstruction(EqualWeightingPortfolioConstructionModel):
       def DetermineTargetPercent(self, activeInsights):
           if activeInsights:
               return {insight: 1/len(activeInsights) for insight in activeInsights}
           return {}
   ```

2. **Ensure Integration with Updated Data Handling:**

   - Confirm that all insights produced from the new option chain subscription flow properly into the PortfolioConstruction model.

### 3.4 Order Lifecycle Consistency

1. **Ensure Order Position Building Matches New Data:**

   - Validate that enriched data (e.g., Greek values from the new models) is used in `buildOrderPosition`.
   - Continue using current multi-leg packaging and insight generation, making sure that price and limit orders reflect updated risk models.

---

## 4. Implementation Plan

1. **Local Branch & Testing:**
   - Create a new branch to integrate these changes.
   - Update unit tests to validate that old and new subscriptions work correctly.
   - Simulate options chain data to ensure that the universe selection model correctly subscribes to and filters contracts.

2. **Step-by-Step Refactoring:**
   - Replace the `SetOptionFilter` method in `DataHandler` and validate that options are being correctly selected.
   - Refactor `optionChainProviderFilter` with the revised filtering policy and ensure that tradability is confirmed.
   - Update the Greek initialization in both `DataHandler` and `SetupBaseStructure`.
   - Finally, test portfolio construction via sample insights.

3. **Performance Verification:**
   - Utilize the built-in `executionTimer` to confirm that changes do not negatively affect processing time.
   - Use the enhanced charting and logging to verify that new values (e.g., Greeks, option symbols) match expectations.

---

## 5. Dependencies & References

- **QuantConnect Documentation:**
  - Option Universe Selection Models and live filtering updates.
  - Built-in Option Greek Models.
  - SecurityInitializer and Brokerage updates.
- **Git Practices:**
  - Use a development branch.
  - Pair changes with unit tests focused on options filtering and position building.

---

This spec provides a clear roadmap with actionable code and a plan for validating the changes. Implementing these improvements will help modernize your algorithm, ensure cleaner data handling, and leverage QuantConnect’s evolving infrastructure.
