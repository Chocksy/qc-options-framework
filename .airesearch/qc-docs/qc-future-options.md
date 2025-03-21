Below is a concise summary of the key points from the QC Future Options documentation – focusing solely on Python examples and essential parameters. FROM: https://www.quantconnect.com/docs/v2/writing-algorithms/universes/future-options

---

# Summary: Future Options Universes

## 1. Introduction
- **Purpose:**  
  Enable selection of option contracts on a defined Futures universe.

---

## 2. Create Universes
- **Process:**  
  Define a futures universe in `initialize` then add its options via `self.add_future_option`.
- **Python Example:**
  
  ```python
  self.universe_settings.asynchronous = True
  future = self.add_future(Futures.Metals.GOLD)
  future.set_filter(0, 90)
  self.add_future_option(future.symbol)
  ```
  
- **Method Arguments for `add_future_option`:**

  | Argument          | Data Type                                                                 | Description                                                                        | Default Value |
  | ----------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------- |
  | `symbol`          | `Symbol`                                                                  | The continuous Future contract Symbol.                                             | N/A           |
  | `option_filter`   | `Callable[[OptionFilterUniverse], OptionFilterUniverse]`                 | A function to filter/select Future Option contracts.                               | `None`        |

- **Optional:**  
  Override the default pricing model by setting a custom security initializer.

  ```python
  seeder = SecuritySeeder.NULL
  self.set_security_initializer(MySecurityInitializer(self.brokerage_model, seeder, self))

  class MySecurityInitializer(BrokerageModelSecurityInitializer):

      def __init__(self, brokerage_model: IBrokerageModel, security_seeder: ISecuritySeeder) -> None:
          super().__init__(brokerage_model, security_seeder)

      def initialize(self, security: Security) -> None:
          super().initialize(security)
          if security.type == SecurityType.FUTURE_OPTION:
              security.price_model = OptionPriceModels.crank_nicolson_fd()
  ```

---

## 3. Filter Contracts
- **Default Subscription:**  
  - Standard contracts (non-weekly by default)
  - Within 1 strike of the underlying asset's price
  - Expiring within 35 days

- **Customization:**  
  Pass a filter via a lambda or a standalone function to `self.add_future_option`.

- **Python Example (Inline Filter):**
  
  ```python
  self.add_future_option(future.symbol, lambda u: u.strikes(-1, 1))
  ```

- **Available Methods on `OptionFilterUniverse`:**

  | Method                                         | Python Method Name         | Description                                                            |
  | ---------------------------------------------- | -------------------------- | ---------------------------------------------------------------------- |
  | `Strikes(int minStrike, int maxStrike)`        | `strikes(min_strike, max_strike)` | Selects contracts within a strike range.                             |
  | `CallsOnly()`                                  | `calls_only()`             | Selects call contracts.                                                |
  | `PutsOnly()`                                   | `puts_only()`              | Selects put contracts.                                                 |
  | `StandardsOnly()`                              | `standards_only()`         | Selects standard contracts.                                            |
  | `IncludeWeeklys()`                             | `include_weeklys()`        | Includes non-standard weekly contracts.                              |
  | `WeeklysOnly()`                                | `weeklys_only()`           | Selects only weekly contracts.                                         |
  | `FrontMonth()`                                 | `front_month()`            | Selects the front month contract.                                      |
  | `BackMonths()`                                 | `back_months()`            | Selects non-front month contracts.                                     |
  | `BackMonth()`                                  | `back_month()`             | Selects the back month contract.                                       |
  | `Expiration(int minExpiryDays, int maxExpiryDays)` | `expiration(min_expiryDays, max_expiryDays)` | Filters by specified expiration range.                    |
  | `Contracts(contracts: List[Symbol])`           | `contracts(contracts)`     | Selects a list of specific contracts.                                  |

- **Chained Filter Example:**

  ```python
  self.add_future_option(future.symbol, lambda u: u.strikes(-1, 1).calls_only())
  ```

- **Isolated Filter Function Example:**

  ```python
  def _contract_selector(self, u: OptionFilterUniverse) -> OptionFilterUniverse:
      symbols = u.puts_only()
      strike = min(symbol.id.strike_price for symbol in symbols)
      symbols = [s for s in symbols if s.id.strike_price == strike]
      return u.contracts(symbols)

  # In initialize:
  self.add_future_option(future.symbol, self._contract_selector)
  ```

---

## 4. Navigate Option Chains
- **Purpose:**  
  Access and filter the chain of option contracts for a given underlying.

- **Processing Steps:**  
  Loop through `slice.option_chains` and sort/filter contracts as needed.

- **Python Example (Filtering OptionChain):**

  ```python
  def on_data(self, slice: Slice) -> None:
      for _, chain in slice.option_chains.items():
          # Find 5 put contracts closest to ATM with the farthest expiration.
          contracts = [x for x in chain if x.right == OptionRight.PUT]
          contracts = sorted(
              sorted(contracts, key=lambda x: abs(chain.underlying.price - x.strike)),
              key=lambda x: x.expiry, reverse=True
          )[:5]
          # Select the contract with delta closest to -0.5.
          contract = sorted(contracts, key=lambda x: abs(-0.5 - x.greeks.delta))[0]
  ```

- **Accessing Canonical Option Chain from Futures Chain:**

  ```python
  def on_data(self, slice: Slice) -> None:
      for future_sym, futures_chain in slice.futures_chains.items():
          future_contract = next(iter(futures_chain))
          canonical_fop_symbol = Symbol.create_canonical_option(future_contract.symbol)
          fop_chain = slice.option_chains.get(canonical_fop_symbol)
          if fop_chain:
              for contract in fop_chain:
                  # Process each contract accordingly
                  pass
  ```

- **Key `OptionChain` Properties:**

  - `underlying`: Base data for the underlying asset.
  - `ticks`: Recent tick data per option symbol.
  - `trade_bars`: Bar data per option symbol.
  - `quote_bars`: Quote data per option symbol.
  - `contracts`: All contracts that passed the filter.
  - `filtered_contracts`: Set of filtered option symbols.
  - `data_frame`: Data frame representation.
  - `data_type`: Market data type.
  - `is_fill_forward`: Indicates fill-forward status.
  - `time` & `end_time`: Data time markers.
  - `symbol`, `value`/`price`: Price information.

---

## 5. Selection Frequency
- **Default Behavior:**  
  Future Option universes select their contracts at the first time step each trading day.

---

## 6. Examples
- **0DTE (Zero Days To Expiration) Contracts:**
  - **Description:**  
    Selects options that expire on the trading day. For example, on the E-mini S&P 500.
  
  - **Python Example:**

    ```python
    class ZeroDTEFutureOptionUniverseAlgorithm(QCAlgorithm):

        def initialize(self) -> None:
            self.set_start_date(2021, 1, 1)
            self.set_end_date(2021, 4, 1)

            future = self.add_future(Futures.Indices.SP_500_E_MINI)
            future.set_filter(0, 90)
            self.add_future_option(
                future.symbol,
                lambda u: u.include_weeklys().expiration(0, 0).strikes(-3, 3)
            )
    ```
