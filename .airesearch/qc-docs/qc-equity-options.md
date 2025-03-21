Below is a concise summary with the key features, including the available options (from tables) and small Python code snippets for each section. FROM: https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity-options

---

# Equity Options Universe Summary

This document describes how to create and filter an Equity Options universe, retrieve option chains, work with Greeks/IV, and get historical data. Each section below summarizes a chapter with its key details and includes sample Python code.

---

## 1. Introduction

- **Overview:** An Equity Options universe lets you select a basket of contracts for one option. LEAN creates a canonical symbol (via `add_option`) that cannot be traded directly but is used to access the option chain.
- **Code Example:**

```python:example/initialize_basic_option.py
class BasicOptionAlgorithm(QCAlgorithm):

    def initialize(self):
        self.universe_settings.asynchronous = True
        option = self.add_option("SPY")
        option.set_filter(self._filter)
        self._symbol = option.symbol

    def _filter(self, universe):
        return universe.include_weeklys().expiration(0, 7).delta(0.35, 0.75)

    def on_data(self, data):
        chain = data.option_chains.get(self._symbol)
        if chain:
            contract = sorted(chain, key=lambda x: (x.expiry, x.greeks.delta))[0]
```

---

## 2. Create Universes

- **How-To:** Use `add_option` in your algorithm’s `initialize` method to subscribe to a universe.
- **Method Attributes:**  
  | Argument                                      | Data Type            | Description                                                                                      | Default Value                |
  | --------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------- |
  | `ticker`                                      | string/str           | The underlying Equity ticker.                                                                    | (none)                       |
  | `resolution`                                  | Resolution?/None     | Market data resolution.                                                                          | None                         |
  | `market`                                      | string/str           | The underlying equity market.                                                                    | None                         |
  | `fillForward`/`fill_forward`                   | bool                 | If true, sends last available data when no current data exists.                                  | True                         |
  | `leverage`                                    | decimal/float        | Leverage for the Equity.                                                                         | Security.NULL_LEVERAGE       |
  | `extendedMarketHours`/`extended_market_hours`  | bool                 | If true, subscribes during pre/post-market hours.                                                | False                        |

- **Code Example:**

```python:example/create_universe.py
class BasicOptionAlgorithm(QCAlgorithm):

    def initialize(self):
        self.universe_settings.asynchronous = True
        option = self.add_option("SPY")
        option.set_filter(self._filter)
        self._symbol = option.symbol

    def _filter(self, universe):
        # Basic filter: include weeklys, expiration between 0 and 7 days, delta between 0.35 and 0.75
        return universe.include_weeklys().expiration(0, 7).delta(0.35, 0.75)
```

---

## 3. Filter by Investment Strategy

- **Overview:** Select contracts to build option strategies (e.g. Straddle, Iron Condor, Strangle).
- **Code Examples:**

```python:example/filter_investment_strategy.py
# Example 1: Straddle
option.set_filter(lambda ofs: ofs.straddle(30, 5, 10))

# Example 2: Iron Condor (including weeklys, strikes -20 to 20, expiration 0 to 30 days)
option.set_filter(lambda ofs: ofs.include_weeklys().strikes(-20, 20).expiration(0, 30).iron_condor(30, 5, 10))

# Example 3: 0DTE Strangle
option.set_filter(lambda ofs: ofs.include_weeklys().expiration(0, 0).strangle(30, 5, -10))
```

- **Filter Methods for Strategies:**

  | Method                                        | Python Method                                                                      | Description                                                       |
  | --------------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
  | `NakedCall(minDaysTillExpiry, strikeFromAtm)`  | `naked_call(min_days_till_expiry, strike_from_atm)`                                | For Naked/Covered/Protective Call strategies                        |
  | `NakedPut(minDaysTillExpiry, strikeFromAtm)`   | `naked_put(min_days_till_expiry, strike_from_atm)`                                 | For Naked/Covered/Protective Put strategies                         |
  | `CallSpread(minDaysTillExpiry, higherStrikeFromAtm, lowerStrikeFromAtm)` | `call_spread(min_days_till_expiry, higher_strike_from_atm, lower_strike_from_atm)` | For Bull/Bear Call Spreads                                          |
  | `PutSpread(minDaysTillExpiry, higherStrikeFromAtm, lowerStrikeFromAtm)`  | `put_spread(min_days_till_expiry, higher_strike_from_atm, lower_strike_from_atm)`  | For Bull/Bear Put Spreads                                           |
  | `CallCalendarSpread(strikeFromAtm, minNearDaysTillExpiry, minFarDaysTillExpiry)` | `call_calendar_spread(strike_from_atm, min_near_days_till_expiry, min_far_days_till_expiry)` | For Call Calendar Spreads      |
  | `PutCalendarSpread(strikeFromAtm, minNearDaysTillExpiry, minFarDaysTillExpiry)`  | `put_calendar_spread(strike_from_atm, min_near_days_till_expiry, min_far_days_till_expiry)`  | For Put Calendar Spreads       |
  | `Strangle(minDaysTillExpiry, higherStrikeFromAtm, lowerStrikeFromAtm)`  | `strangle(min_days_till_expiry, higher_strike_from_atm, lower_strike_from_atm)`  | For Strangle strategies                                             |
  | `Straddle(minDaysTillExpiry)`                 | `straddle(min_days_till_expiry)`                                                   | For Straddle strategies                                             |
  | `ProtectiveCollar(minDaysTillExpiry, higherStrikeFromAtm, lowerStrikeFromAtm)` | `protective_collar(min_days_till_expiry, higher_strike_from_atm, lower_strike_from_atm)` | For Protective Collar                                              |
  | `Conversion(minDaysTillExpiry, strikeFromAtm)`  | `conversion(min_days_till_expiry, strike_from_atm)`                                | For Conversion/Reverse Conversion                                   |
  | `CallButterfly(minDaysTillExpiry, strikeSpread)`| `call_butterfly(min_days_till_expiry, strike_spread)`                              | For Call Butterfly strategies                                       |
  | `PutButterfly(minDaysTillExpiry, strikeSpread)` | `put_butterfly(min_days_till_expiry, strike_spread)`                               | For Put Butterfly strategies                                        |
  | `IronButterfly(minDaysTillExpiry, strikeSpread)`| `iron_butterfly(min_days_till_expiry, strike_spread)`                              | For Iron Butterfly                                                  |
  | `IronCondor(minDaysTillExpiry, nearStrikeSpread, farStrikeSpread)` | `iron_condor(min_days_till_expiry, near_strike_spread, far_strike_spread)`            | For Iron Condor                                                     |
  | `BoxSpread(minDaysTillExpiry, strikeSpread)`    | `box_spread(min_days_till_expiry, strike_spread)`                                  | For Box Spread                                                      |
  | `JellyRoll(strikeFromAtm, minNearDaysTillExpiry, minFarDaysTillExpiry)` | `jelly_roll(strike_from_atm, min_near_days_till_expiry, min_far_days_till_expiry)`    | For Jelly Roll                                                      |
  | `CallLadder(minDaysTillExpiry, higherStrikeFromAtm, middleStrikeFromAtm, lowerStrikeFromAtm)` | `call_ladder(min_days_till_expiry, higher_strike_from_atm, middle_strike_from_atm, lower_strike_from_atm)` | For Call Ladder strategies |
  | `PutLadder(minDaysTillExpiry, higherStrikeFromAtm, middleStrikeFromAtm, lowerStrikeFromAtm)`  | `put_ladder(min_days_till_expiry, higher_strike_from_atm, middle_strike_from_atm, lower_strike_from_atm)`  | For Put Ladder strategies  |

---

## 4. Filter by Implied Volatility and Greeks

- **Overview:** Filter contracts based on metrics such as delta, gamma, vega, theta, rho, implied volatility (IV), and open interest.
- **Code Examples:**

```python:example/filter_iv_greeks.py
# Filter by delta
option.set_filter(lambda u: u.delta(0.25, 0.75))

# Include weeklys; filter by IV (0–20%) and expiration in 90 days
option.set_filter(lambda u: u.include_weeklys().iv(0, 20).expiration(0, 90))

# Filter for IV below 20%, expiration 0–30 days, and Iron Condor strategy
option.set_filter(lambda u: u.include_weeklys().iv(0, 20).expiration(0, 30).iron_condor(30, 5, 10))
```

- **Filter Methods for IV and Greeks:**

  | Method                         | Python Method                     | Description                                                     |
  | ------------------------------ | --------------------------------- | --------------------------------------------------------------- |
  | IV(min, max)                   | iv(min, max)                      | Filters by implied volatility.                                  |
  | ImpliedVolatility(min, max)    | implied_volatility(min, max)      | Alias for iv.                                                   |
  | D(min, max)                    | d(min, max)                       | Filters by delta.                                               |
  | Delta(min, max)                | delta(min, max)                   | Alias for d.                                                    |
  | G(min, max)                    | g(min, max)                       | Filters by gamma.                                               |
  | Gamma(min, max)                | gamma(min, max)                   | Alias for g.                                                    |
  | R(min, max)                    | r(min, max)                       | Filters by rho.                                                 |
  | Rho(min, max)                  | rho(min, max)                     | Alias for r.                                                    |
  | V(min, max)                    | v(min, max)                       | Filters by vega.                                                |
  | Vega(min, max)                 | vega(min, max)                    | Alias for v.                                                    |
  | T(min, max)                    | t(min, max)                       | Filters by theta.                                               |
  | Theta(min, max)                | theta(min, max)                   | Alias for t.                                                    |
  | OI(min, max)                   | oi(min, max)                      | Filters by open interest.                                       |
  | OpenInterest(min, max)         | open_interest(min, max)           | Alias for oi.                                                   |

---

## 5. Filter by Other Contract Properties

- **Overview:** Filter based on strike price proximity, expiration range, and contract type.
- **Code Examples:**

```python:example/filter_other_properties.py
from datetime import timedelta

# Filter by strike levels near the underlying price
option.set_filter(min_strike=-1, max_strike=1)

# Filter by expiration range (e.g., contracts expiring in 0-30 days)
option.set_filter(min_expiry=timedelta(days=0), max_expiry=timedelta(days=30))

# Combined filter: strike and expiration range
option.set_filter(min_strike=-1, max_strike=1, min_expiry=timedelta(days=0), max_expiry=timedelta(days=30))

# Filter for call contracts only
option.set_filter(lambda u: u.calls_only())
```

- **Available Filter Techniques:**

  | Technique                                               | Python Version                                              | Description                                                       |
  | ------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------- |
  | SetFilter(minStrike, maxStrike)                         | set_filter(min_strike, max_strike)                          | Filter by strike range relative to the underlying price.          |
  | SetFilter(minExpiry, maxExpiry)                         | set_filter(min_expiry, max_expiry)                          | Filter by a range of expiration dates.                            |
  | SetFilter(minStrike, maxStrike, minExpiry, maxExpiry)     | set_filter(min_strike, max_strike, min_expiry, max_expiry)    | Combine strike and expiry filters.                                |
  | SetFilter(func)                                         | set_filter(lambda u: ... )                                  | Use a custom function filter (e.g., calls_only, puts_only).         |

---

## 6. Default Filter

- **Overview:**  
  By default, LEAN subscribes to standard (non-weekly) option contracts that are within 1 strike of the underlying and expire within 35 days.
- **Note:** No custom code is required unless a different universe is desired.

---

## 7. Navigate Intraday Option Chains

- **Overview:**  
  Retrieve the full option chain from current slice data using the canonical symbol.
- **Code Example:**

```python:example/navigate_intraday.py
def on_data(self, data):
    chain = data.option_chains.get(self._symbol)
    if chain:
        # Example: Select 5 put contracts closest to ATM with the farthest expiration
        contracts = sorted(
            [x for x in chain if x.right == OptionRight.PUT],
            key=lambda x: (x.expiry, abs(chain.underlying.price - x.strike)),
            reverse=True
        )[:5]
        # Pick the contract with delta closest to -0.5
        contract = sorted(contracts, key=lambda x: abs(-0.5 - x.greeks.delta))[0]
```

---

## 8. Navigate Daily Option Chains

- **Overview:**  
  For daily, pre-calculated Greeks and IV, use the `option_chain` API to retrieve a chain (or a DataFrame version).
- **Code Example:**

```python:example/navigate_daily.py
def rebalance(self):
    daily_chain = self.option_chain(self._symbol, flatten=True)
    # DataFrame view:
    df = daily_chain.data_frame
    # Iterate over OptionUniverse objects:
    for option_universe in daily_chain:
        close_price = option_universe.close
        open_interest = option_universe.open_interest
        delta = option_universe.greeks.delta
```

---

## 9. Greeks and Implied Volatility

- **Overview:**  
  Greeks/IV are computed from prior close data. For intraday or custom models, use indicators.
- **Code Example:**

```python:example/initialize_greeks.py
def initialize(self):
    option = self.add_option("SPY")
    # Use a filter that relies on pre-calculated Greeks (e.g., delta between 0.3 and 0.7)
    option.set_filter(lambda u: u.include_weeklys().delta(0.3, 0.7).expiration(0, 7))
```

---

## 10. Historical Data

- **Overview:**  
  Retrieve historical option chain data using the `history[OptionUniverse]` method. The historical data includes all tradable contracts from previous trading days.
- **Code Example:**

```python:example/historical_data.py
def initialize(self):
    self.set_start_date(2020, 1, 1)
    option = self.add_option("SPY")
    # Get historical data as a DataFrame:
    history_df = self.history(option.symbol, 5, flatten=True)
    # Get OptionUniverse objects:
    history = self.history[OptionUniverse](option.symbol, 5)
    for chain in history:
        # Filter by a condition on Greeks (e.g., delta > 0.3)
        filtered_contracts = [c for c in chain if c.greeks.delta > 0.3]
        for contract in filtered_contracts:
            symbol = contract.symbol
            expiry = contract.id.date
            strike = contract.id.strike_price
            price = contract.close
            iv = contract.implied_volatility
```

---

## 11. Selection Frequency

- **Overview:**  
  Option universe filters run at the first time step of each day by default, ensuring daily refreshed contract selection.

---

## 12. Examples: 0DTE Contracts

- **Overview:**  
  0DTE (zero days to expiration) contracts expire the same day. A common strategy is to select contracts falling within a few strikes of the underlying.
- **Code Example:**

```python:example/zero_dte.py
class ZeroDTEOptionUniverseAlgorithm(QCAlgorithm):

    def initialize(self):
        option = self.add_option('SPY')
        option.set_filter(lambda u: u.include_weeklys().expiration(0, 0).strikes(-3, 3))
```
