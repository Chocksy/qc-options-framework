Below is a concise, Python-only summary that highlights the key chapters/features of the Index Options document, including the Python examples and complete tables for method arguments. FROM: https://www.quantconnect.com/docs/v2/writing-algorithms/universes/index-options

---

## 1. Introduction

**Detail**:  
An Index Option universe lets you select a basket of Option contracts on an underlying index.

---

## 2. Create Universes

There are two universe types:

### Non-Standard Universes

**Detail**:  
Use an underlying index symbol with a target Option ticker (e.g. weekly index options).  
**Python Example**:
```python
class WeeklyIndexOptionAlgorithm(QCAlgorithm):

    def initialize(self):
        underlying = self.add_index("VIX").symbol
        option = self.add_index_option(underlying, "VIXW")
        option.set_filter(lambda universe: universe.include_weeklys().expiration(0, 7).delta(0.35, 0.75))
        self._symbol = option.symbol

    def on_data(self, data):
        chain = data.option_chains.get(self._symbol)
        if chain:
            contract = sorted(chain, key=lambda x: (x.expiry, x.greeks.delta))[0]
```

**Method Arguments for Non-Standard Universes**:

| Argument                    | Data Type  | Description                                                                                                    | Default Value |
|-----------------------------|------------|----------------------------------------------------------------------------------------------------------------|---------------|
| underlying                  | Symbol     | The underlying Index Symbol. See Supported Assets.                                                           | –             |
| targetOption (target_option)| string     | The target Option ticker. See Supported Assets.                                                              | –             |
| resolution                  | Resolution?| The market data resolution; index resolution must be ≤ index option resolution.                                | None          |
| market                      | string     | The Index Option market.                                                                                       | Market.USA    |
| fillForward (fill_forward)  | bool       | If true, the slice contains the last available data when data is missing.                                      | True          |

---

### Standard Universes

**Detail**:  
Set up a universe with just an index ticker (e.g. "SPX").  
**Python Example**:
```python
option = self.add_index_option("SPX")
option.set_filter(lambda universe: universe.expiration(0, 60).delta(0.35, 0.75))
self._symbol = option.symbol
```

**Method Arguments for Standard Universes**:

| Argument    | Data Type  | Description                                      | Default Value |
|-------------|------------|--------------------------------------------------|---------------|
| ticker      | string     | The underlying Index ticker.                     | –             |
| resolution  | Resolution?| The market data resolution.                      | None          |
| market      | string     | The Index Option market.                         | Market.USA    |
| fillForward | bool       | If true, the last available data is provided.    | True          |

---

## 3. Filter by Investment Strategy

**Detail**:  
Filter selection by choosing Option strategies (e.g. Straddle, Iron Condor, Strangle).

**Python Examples**:
```python
# Straddle
option.set_filter(lambda universe: universe.straddle(30, 5, 10))

# Iron Condor (with weeklys, expiration in 30 days)
option.set_filter(lambda universe: universe.include_weeklys().strikes(-20, 20).expiration(0, 30).iron_condor(30, 5, 10))

# Strangle (0DTE)
option.set_filter(lambda universe: universe.include_weeklys().expiration(0, 0).strangle(30, 5, -10))
```

**Strategy Filter Methods**:

| Method             | Python Signature                                                                                                      | Description                                                                                               |
|--------------------|-----------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| naked_call         | naked_call(min_days_till_expiry: int, strike_from_atm: float)                                                         | Selects a call for Naked, Covered, or Protective Call strategies.                                         |
| naked_put          | naked_put(min_days_till_expiry: int, strike_from_atm: float)                                                          | Selects a put for Naked, Covered, or Protective Put strategies.                                           |
| call_spread        | call_spread(min_days_till_expiry: int, higher_strike_from_atm: float, lower_strike_from_atm: float)                     | Selects two calls for Bull/Bear Call Spread.                                                               |
| put_spread         | put_spread(min_days_till_expiry: int, higher_strike_from_atm: float, lower_strike_from_atm: float)                      | Selects two puts for Bull/Bear Put Spread.                                                                 |
| call_calendar_spread | call_calendar_spread(strike_from_atm: float, min_near_days_till_expiry: int, min_far_days_till_expiry: int)                | Selects two calls for Calendar Spreads.                                                                   |
| put_calendar_spread  | put_calendar_spread(strike_from_atm: float, min_near_days_till_expiry: int, min_far_days_till_expiry: int)                 | Selects two puts for Calendar Spreads.                                                                    |
| strangle           | strangle(min_days_till_expiry: int, higher_strike_from_atm: float, lower_strike_from_atm: float)                        | Selects two contracts for a Long/Short Strangle.                                                          |
| straddle           | straddle(min_days_till_expiry: int)                                                                                   | Selects two contracts for a Long/Short Straddle.                                                          |
| protective_collar  | protective_collar(min_days_till_expiry: int, higher_strike_from_atm: float, lower_strike_from_atm: float)                | Selects two contracts for Protective Collar.                                                              |
| conversion         | conversion(min_days_till_expiry: int, strike_from_atm: float)                                                         | Selects two contracts for Conversion or Reverse Conversion.                                             |
| call_butterfly     | call_butterfly(min_days_till_expiry: int, strike_spread: float)                                                       | Selects three contracts for Long/Short Call Butterfly.                                                    |
| put_butterfly      | put_butterfly(min_days_till_expiry: int, strike_spread: float)                                                        | Selects three contracts for Long/Short Put Butterfly.                                                     |
| iron_butterfly     | iron_butterfly(min_days_till_expiry: int, strike_spread: float)                                                       | Selects four contracts for Long/Short Iron Butterfly.                                                     |
| iron_condor        | iron_condor(min_days_till_expiry: int, near_strike_spread: float, far_strike_spread: float)                             | Selects four contracts for Long/Short Iron Condor.                                                        |
| box_spread         | box_spread(min_days_till_expiry: int, strike_spread: float)                                                           | Selects four contracts for Box Spread.                                                                    |
| jelly_roll         | jelly_roll(strike_from_atm: float, min_near_days_till_expiry: int, min_far_days_till_expiry: int)                        | Selects four contracts for Jelly Roll.                                                                    |
| call_ladder        | call_ladder(min_days_till_expiry: int, higher_strike_from_atm: float, middle_strike_from_atm: float, lower_strike_from_atm: float) | Selects four contracts for Bear/Bull Call Ladder.                                                         |
| put_ladder         | put_ladder(min_days_till_expiry: int, higher_strike_from_atm: float, middle_strike_from_atm: float, lower_strike_from_atm: float)  | Selects four contracts for Bear/Bull Put Ladder.                                                         |

---

## 4. Filter by Implied Volatility and Greeks

**Detail**:  
Filters using pre-calculated daily values of IV and Greeks.

**Python Examples**:
```python
# Delta between 0.25 and 0.75
option.set_filter(lambda u: u.delta(0.25, 0.75))

# With weeklys: IV below 20% and expires in 90 days
option.set_filter(lambda u: u.include_weeklys().iv(0, 20).expiration(0, 90))

# With weeklys: Expire in 30 days, IV below 20%, forming an Iron Condor
option.set_filter(lambda u: u.include_weeklys().iv(0, 20).expiration(0, 30).iron_condor(30, 5, 10))
```

**IV & Greeks Filter Methods**:

| Method          | Python Signature                                               | Description                                    |
|-----------------|----------------------------------------------------------------|------------------------------------------------|
| iv / implied_volatility  | iv(min: float, max: float) or implied_volatility(min: float, max: float) | Filters by implied volatility.                 |
| delta           | delta(min: float, max: float)                                   | Filters by delta.                              |
| gamma           | gamma(min: float, max: float)                                   | Filters by gamma.                              |
| rho             | rho(min: float, max: float)                                     | Filters by rho.                                |
| vega            | vega(min: float, max: float)                                    | Filters by vega.                               |
| theta           | theta(min: float, max: float)                                   | Filters by theta.                              |
| open_interest   | open_interest(min: float, max: float)                           | Filters by open interest.                      |

---

## 5. Filter by Other Contract Properties

**Detail**:  
Filters contracts based on strike levels, expiration, and type (calls/puts).

**Python Examples**:
```python
# Strike range around underlying price
option.set_filter(min_strike=-1, max_strike=1)

# Expiration within 30 days
option.set_filter(min_expiry=timedelta(days=0), max_expiry=timedelta(days=30))

# Call contracts only
option.set_filter(lambda u: u.calls_only())
```

**Filtering Techniques**:

| Method                                          | Python Signature                                                                                | Description                                                                                |
|-------------------------------------------------|-------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| set_filter(min_strike, max_strike)              | set_filter(min_strike: int, max_strike: int)                                                      | Filter by strike range relative to underlying price.                                       |
| set_filter(min_expiry, max_expiry)              | set_filter(min_expiry: timedelta, max_expiry: timedelta)                                          | Filter by expiration range.                                                                |
| set_filter(min_strike, max_strike, min_expiry, max_expiry)| set_filter(min_strike: int, max_strike: int, min_expiry: timedelta, max_expiry: timedelta)   | Combined strike and expiration filter.                                                     |
| calls_only                                      | calls_only()                                                                                    | Only include call contracts.                                                               |
| puts_only                                       | puts_only()                                                                                     | Only include put contracts.                                                                |
| standards_only                                  | standards_only()                                                                                | Only include standard contracts.                                                           |
| include_weeklys                                 | include_weeklys()                                                                               | Include non-standard weekly contracts.                                                     |
| weeklys_only                                    | weeklys_only()                                                                                  | Only include weekly contracts.                                                             |
| front_month                                     | front_month()                                                                                   | Select the front month contract.                                                           |
| back_months                                     | back_months()                                                                                   | Select non-front month contracts.                                                          |
| back_month                                      | back_month()                                                                                    | Select back month contracts.                                                               |
| expiration                                      | expiration(min_expiry_days: int, max_expiry_days: int)                                            | Filter by expiration (relative to current day).                                            |
| contracts                                       | contracts(contracts: List[Symbol])                                                              | Filter by a given list of contracts.                                                       |
| contracts (with selector)                       | contracts(contract_selector: Callable[[List[Symbol]], List[Symbol]])                              | Filter using a selector function.                                                          |

---

## 6. Default Filter

**Detail**:  
If no filter is set, LEAN subscribes to standard contracts that are within 1 strike of the underlying price and expire within 35 days.

---

## 7. Navigate Intraday Option Chains

**Detail**:  
Access the OptionChain in the `on_data` call. The chain holds contract data, underlying price, ticks, trade/quote bars, etc.

**Python Example**:
```python
def on_data(self, data):
    chain = data.option_chains.get(self._symbol)
    if chain:
        # Find 5 put contracts closest to ATM and with farthest expiry
        contracts = sorted(
            [x for x in chain if x.right == OptionRight.PUT],
            key=lambda x: (x.expiry, abs(chain.underlying.price - x.strike))
        )[:5]
        # Choose the one with delta closest to -0.5
        contract = sorted(contracts, key=lambda x: abs(-0.5 - x.greeks.delta))[0]
```

---

## 8. Navigate Daily Option Chains

**Detail**:  
For daily pre-calculated Greeks and IV, use the `option_chain` method to retrieve an OptionUniverse. Data can be accessed as a DataFrame or iterated contract by contract.

**Python Example**:
```python
def _rebalance(self):
    daily_chain = self.option_chain(self._symbol, flatten=True)
    df = daily_chain.data_frame
    for option_universe in daily_chain:
        close = option_universe.close
        oi = option_universe.open_interest
        delta = option_universe.greeks.delta
```

---

## 9. Greeks and Implied Volatility

**Detail**:  
Use pre-calculated Greeks/IV or override with your own models. You can set a custom pricing model.

**Python Example**:
```python
option.price_model = OptionPriceModels.crank_nicolson_fd()
```

---

## 10. Historical Data

**Detail**:  
Retrieve historical OptionUniverse data to review full chains from past trading days.

**Python Example**:
```python
def initialize(self):
    self.set_start_date(2020, 1, 1)
    option = self.add_index_option('SPX')
    history_df = self.history(option.symbol, 5, flatten=True)
    history = self.history[OptionUniverse](option.symbol, 5)
    for chain in history:
        for contract in chain:
            print(contract.symbol, contract.close, contract.implied_volatility)
```

---

## 11. Selection Frequency

**Detail**:  
Index Option universes are selected at the first time step of each day.

---

## 12. Examples: 0DTE Contracts

**Detail**:  
A full example that selects 0DTE contracts (expiring on the same day) within a strike range.
  
**Python Example**:
```python
class ZeroDTEIndexOptionUniverseAlgorithm(QCAlgorithm):
    def initialize(self):
        index = self.add_index('SPX')
        index_option = self.add_index_option(index.symbol, 'SPXW')
        index_option.set_filter(lambda u: u.include_weeklys().expiration(0, 0).strikes(-3, 3))
```

---

This summary captures the key chapters with short details, Python examples, and complete tables for method attributes—providing a foundation to expand your algo code.
