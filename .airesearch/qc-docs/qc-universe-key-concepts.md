Below is a concise summary of the key universe selection features (in Python) along with a minimal code snippet for each section and the full table of universe options. FROM: https://www.quantconnect.com/docs/v2/writing-algorithms/universes/key-concepts

---

## Universes Summary

### 1. Introduction
- **What:** Define your tradeable assets basket.
- **How:** A filter function receives a large dataset and returns a list of symbols.
- **Benefit:** Enables dynamic universe selection to reduce selection bias.

---

### 2. Selection Functions
- **What:** Filter function to choose assets (e.g. top 100 liquid equities).
- **Key Detail:** Sort fundamentals by dollar volume then take the top N.
  
```python:my_algo.py
class MyFundamentalUniverseAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.universe_settings.asynchronous = True
        self.add_universe(self._fundamental_filter_function)

    def _fundamental_filter_function(self, fundamentals: List[Fundamental]) -> List[Symbol]:
        sorted_fundamentals = sorted(fundamentals, key=lambda f: f.dollar_volume, reverse=True)
        return [f.symbol for f in sorted_fundamentals[:100]]
```

---

### 3. Security Changed Events
- **What:** Handle assets entering and leaving the universe.
- **Key Detail:** In the event handler, check added/removed securities; liquidate if needed.

```python:my_algo.py
def on_securities_changed(self, changes: SecurityChanges) -> None:
    for security in changes.added_securities:
        self.debug(f"{self.time}: Added {security.symbol}")
    for security in changes.removed_securities:
        self.debug(f"{self.time}: Removed {security.symbol}")
        if security.invested:
            self.liquidate(security.symbol, "Removed from Universe")
```

---

### 4. Custom Security Properties
- **What:** Inject custom attributes (e.g., an SMA indicator) into a security.
- **Key Detail:** Use duck typing to attach properties and warm them up.

```python:my_algo.py
def on_securities_changed(self, changes: SecurityChanges) -> None:
    for security in changes.added_securities:
        security.indicator = self.sma(security.symbol, 10)
        self.warm_up_indicator(security.symbol, security.indicator)
    for security in changes.removed_securities:
        self.deregister_indicator(security.indicator)
```

---

### 5. Select Current Constituents
- **What:** Leave the universe unchanged.
- **Key Detail:** Return `Universe.UNCHANGED` from your filter function.

```python:my_algo.py
class MyUniverseAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.universe_settings.asynchronous = True
        self.add_universe(self._my_fundamental_filter_function)

    def _my_fundamental_filter_function(self, fundamentals: List[Fundamental]) -> List[Symbol]:
        return Universe.UNCHANGED
```

---

### 6. Universe Manager
- **What:** Access multiple universes and track their members.
- **Key Detail:** Save a reference to the universe when adding it and use the universe manager to inspect members.

```python:my_algo.py
self.universe_settings.asynchronous = True
self._universe = self.add_universe(self._my_fundamental_filter_function)
universe_members = self.universe_manager[self._universe.configuration.symbol].members
for sym, security in universe_members.items():
    # Process each security: sym is the asset symbol
    pass
```

---

### 7. Active & Selected Securities
- **Active Securities:** Collection of all subscribed securities.
  
  ```python:my_algo.py
  for security in self.securities.total:
      pass

  for security in self.securities.values():
      pass
  ```

- **Selected Securities:** The current universe selection (may be fewer than active due to orders/positions).

  ```python:my_algo.py
  class SimpleRebalancingAlgorithm(QCAlgorithm):
      def initialize(self):
          symbol = Symbol.create("SPY", SecurityType.EQUITY, Market.USA)
          date_rule = self.date_rules.week_start(symbol)
          self.universe_settings.schedule.on(date_rule)
          universe = self.add_universe(self.universe.dollar_volume.top(5))
          self.schedule.on(
              date_rule,
              self.time_rules.after_market_open(symbol, 30),
              lambda: self.set_holdings(
                  [PortfolioTarget(sym, 1/len(universe.selected)) for sym in universe.selected],
                  True
              )
          )
  ```

---

### 8. Derivative Universes
- **What:** Use derivative universes for contracts (options, futures, etc.).
- **Key Detail:** Options include equity options, future options, index options, etc.
- **Note:** No direct code snippet provided.

---

### 9. Historical Asset Prices
- **What:** Efficiently maintain historical price data across all assets.
- **Key Detail:** Create a DataFrame (or Dictionary) to store historical price points and update daily.
  
```python:my_algo.py
class MaintainHistoricalDailyUniversePriceDataAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 1)
        self.set_cash(1_000_000)
        self.universe_settings.resolution = Resolution.DAILY
        self._universe = self.add_universe(lambda fundamentals: [f.symbol for f in sorted(fundamentals, key=lambda f: f.market_cap)[-10:]])
        self._all_history = pd.DataFrame()
        self._lookback = 252
        spy = Symbol.create('SPY', SecurityType.EQUITY, Market.USA)
        self.schedule.on(self.date_rules.every_day(spy), self.time_rules.at(0, 1), self._rebalance)

    def on_securities_changed(self, changes):
        for security in changes.removed_securities:
            if security.symbol in self._all_history.columns:
                self._all_history.drop(security.symbol, axis=1, inplace=True)
        history_data = self.history(
            [security.symbol for security in changes.added_securities],
            self._lookback + 1,
            Resolution.DAILY
        )
        if not history_data.empty:
            self._all_history = self._all_history.join(history_data.open.unstack(0).iloc[:-1], how='outer')

    def _rebalance(self):
        new_data = self.history(list(self._universe.selected), 1, Resolution.DAILY).open.unstack(0)
        self._all_history = pd.concat([self._all_history, new_data])
        self._all_history = self._all_history.iloc[-self._lookback:]
        valid_history = self._all_history[[sym for sym in self._all_history.columns if self.securities[sym].price]]
        signals = 1 / valid_history.dropna(axis=1).corr().abs().sum()
        signals /= signals.sum()
        self.set_holdings([PortfolioTarget(sym, sig) for sym, sig in signals.items()], True)
```

---

### 10. Universes Table
The complete list of asset classes, universe types, and example URLs:

| **Asset Class**   | **Universe Type**                  | **Example URL**                                                                                                                                          |
|-------------------|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Equities          | Liquidity Universes                | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/liquidity-universes#99-Examples)                                       |
| Equities          | Fundamental Universes              | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/fundamental-universes#99-Examples)                                      |
| Equities          | ETF Constituents Universes         | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/etf-constituents-universes#99-Examples)                                   |
| Equities          | Chained Universes                  | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/chained-universes#05-Chain-Fundamental-and-Alternative-Data)             |
| Equities          | Alternative Data Universes         | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/alternative-data-universes#99-Examples)                                  |
| Equity Options    | Equity Option Universes            | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity-options#99-Examples)                                                      |
| CFDs              | Equity CFD Universes               | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity-cfd#99-Examples)                                                           |
| Futures           | Future Universes                   | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures#99-Examples)                                                             |
| Future Options    | Future Option Universes            | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/future-options#99-Examples)                                                      |
| Index Options     | Index Option Universes             | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/liquidity-universes#99-Examples)                                           |
| Cryptos           | Crypto Universes                   | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/crypto#99-Examples)                                                              |
| Any               | Custom Universes                   | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/custom-universes#99-Examples)                                                    |
| Any               | Dataless Scheduled Universes       | [Example](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/dataless-scheduled-universes#99-Examples)                                           |
