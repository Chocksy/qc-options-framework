# Universes Documentation Summary

This document summarizes key universe settings and configuration options for algorithm construction. FROM: https://www.quantconnect.com/docs/v2/writing-algorithms/universes/settings

---

## 1. Introduction
Universe settings configure asset properties and security initializers.

---

## 2. Resolution
**Purpose:** Defines the time period of asset data using the `Resolution` enum.  
**Python Example:**
```python
# Add daily Equity Option data for SPY.
self.add_option("SPY", resolution=Resolution.DAILY)
```

---

## 3. Leverage
**Purpose:** Sets the maximum leverage (float) for each asset in a non-derivative universe.  
**Python Example:**
```python
# Assign 2x leverage for all securities in the universe.
self.universe_settings.leverage = 2.0
self.add_universe(self.universe.dollar_volume.top(50))
```

---

## 4. Fill Forward
**Purpose:** Determines if data should be fill-forward (bool, default True).  
**Python Example (non-derivative):**
```python
# Disable fill-forward data.
self.universe_settings.fill_forward = False
self.add_universe(self.universe.dollar_volume.top(50))
```
**Python Example (derivative):**
```python
# Disable fill-forward for an index option universe.
self.add_index_option("VIX", fill_forward=False)
```

---

## 5. Extended Market Hours
**Purpose:** Enables receiving data outside regular trading hours (bool, default False).  
**Python Example (non-derivative):**
```python
# Enable extended market hours data.
self.universe_settings.extended_market_hours = True
self.add_universe(self.universe.dollar_volume.top(50))
```
**Python Example (derivative):**
```python
# Enable extended hours for a Futures universe.
self.add_future(Futures.Currencies.BTC, extended_market_hours=True)
```

---

## 6. Minimum Time in Universe
**Purpose:** Specifies the minimum time an asset remains in the universe (timedelta, default 1 day).  
**Python Example:**
```python
# Keep each security in the universe for a minimum of 7 days.
self.universe_settings.minimum_time_in_universe = timedelta(7)
self.add_universe(self.universe.dollar_volume.top(50))
```

---

## 7. Data Normalization Mode
**Purpose:** Adjusts historical data for corporate actions or contracts using an enum.  
- **US Equities Example:**
```python
# Use raw price data (no adjustments for splits/dividends).
self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW
self.add_universe(self.universe.dollar_volume.top(50))
```
- **Futures Example:**
```python
# Set normalization mode for continuous futures contract.
self.add_future(Futures.Currencies.BTC, data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO)
```

---

## 8. Contract Depth Offset
**Purpose:** Chooses which futures contract to use (int, default 0).  
**Python Example:**
```python
# Use the second back month contract.
self.add_future(Futures.Currencies.BTC, contract_depth_offset=3)
```

---

## 9. Asynchronous Selection
**Purpose:** Enables asynchronous universe selection for improved performance (bool, default False).  
**Python Example:**
```python
# Enable asynchronous universe selection.
self.universe_settings.asynchronous = True
self.add_universe(self.universe.dollar_volume.top(50))
```

---

## 10. Schedule
**Purpose:** Defines when universe selection occurs via custom date rules.  
**Python Example (monthly selection):**
```python
self.universe_settings.schedule.on(self.date_rules.month_start())
self.add_universe(self.universe.dollar_volume.top(50))
```

**Supported DateRules Options:**

| Member                                                                                           | Description                                                                            |
| ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| `self.date_rules.set_default_time_zone(time_zone)`                                               | Sets the default time zone for date rules.                                             |
| `self.date_rules.on(year, month, day)`                                                           | Trigger an event on a specific date.                                                   |
| `self.date_rules.on(dates: List[datetime])`                                                      | Trigger an event on specific dates.                                                    |
| `self.date_rules.every_day()`                                                                    | Trigger an event every day.                                                            |
| `self.date_rules.every_day(symbol, extended_market_hours=False)`                                 | Trigger daily for a specified symbol.                                                  |
| `self.date_rules.every(days: List[DayOfWeek])`                                                   | Trigger on specific days of the week.                                                  |
| `self.date_rules.month_start(days_offset=0)`                                                     | First day of month plus an optional offset.                                            |
| `self.date_rules.month_start(symbol, days_offset=0)`                                             | First tradable day for a symbol at month start.                                        |
| `self.date_rules.month_end(days_offset=0)`                                                       | Last day of month minus an offset.                                                     |
| `self.date_rules.month_end(symbol, days_offset=0)`                                               | Last tradable day for a symbol at month end.                                           |
| `self.date_rules.week_start(days_offset=0)`                                                      | First day of week plus an offset.                                                      |
| `self.date_rules.week_start(symbol, days_offset=0)`                                              | First tradable day for a symbol at week start.                                         |
| `self.date_rules.week_end(days_offset=0)`                                                        | Last day of week minus an offset.                                                      |
| `self.date_rules.week_end(symbol, days_offset=0)`                                                | Last tradable day for a symbol at week end.                                            |
| `self.date_rules.year_start(days_offset=0)`                                                      | First day of year plus an offset.                                                      |
| `self.date_rules.year_start(symbol, days_offset=0)`                                              | First tradable day for a symbol at year start.                                         |
| `self.date_rules.year_end(days_offset=0)`                                                        | Last day of year minus an offset.                                                      |
| `self.date_rules.year_end(symbol, days_offset=0)`                                                | Last tradable day for a symbol at year end.                                            |
| `self.date_rules.today`                                                                          | Trigger once today.                                                                    |
| `self.date_rules.tomorrow`                                                                       | Trigger once tomorrow.                                                                 |

*Custom Date Rule Example (10th day of each month):*
```python
date_rule = FuncDateRule(
    name="10th_day_of_the_month",
    get_dates_function=lambda start, end: [
        datetime(year, month, 10)
        for year in range(start.year, end.year)
        for month in range(1, 13)
    ]
)
```

---

## 11. Configure Universe Securities
**Purpose:** Configure per-security settings using security initializers.  
**Python Examples:**

*Using a custom function:*
```python
def custom_security_initializer(security: Security) -> None:
    security.set_fee_model(ConstantFeeModel(0, "USD"))

self.set_security_initializer(custom_security_initializer)
```

*Using a lambda:*
```python
self.set_security_initializer(lambda security: security.set_fee_model(ConstantFeeModel(0, "USD")))
```

*Seeding with last known prices:*
```python
seeder = FuncSecuritySeeder(self.get_last_known_prices)
self.set_security_initializer(lambda security: seeder.seed_security(security))
```

*Extending the default initializer (via subclassing):*
```python
class MySecurityInitializer(BrokerageModelSecurityInitializer):
    def __init__(self, brokerage_model, security_seeder):
        super().__init__(brokerage_model, security_seeder)
        
    def initialize(self, security: Security) -> None:
        super().initialize(security)
        security.set_fee_model(ConstantFeeModel(0, "USD"))

self.set_security_initializer(MySecurityInitializer(
    self.brokerage_model, FuncSecuritySeeder(self.get_last_known_prices)
))
```

---

## 12. Example: Weekly-Updating Liquid Universe Algorithm
**Purpose:** Implements a weekly-updating universe using EMA for trend trading.  
**Python Example:**
```python
class UniverseSettingsAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.set_start_date(2021, 1, 1)
        self.set_end_date(2021, 2, 1)

        # Update the universe weekly.
        self.universe_settings.schedule.on(self.date_rules.week_start())
        self.universe_settings.minimum_time_in_universe = timedelta(7)
        self.universe_settings.resolution = Resolution.DAILY
        self.universe_settings.leverage = 2
        self.universe_settings.extended_market_hours = False
        self.universe_settings.data_normalization_mode = DataNormalizationMode.SPLIT_ADJUSTED

        # Trade on the top 10 most liquid stocks.
        self.add_universe(self.universe.dollar_volume.top(10))

    def on_data(self, slice: Slice) -> None:
        for symbol, bar in slice.bars.items():
            ema = self.securities[symbol].ema.current.value
            if bar.close > ema:
                self.set_holdings(symbol, 0.05)
            else:
                self.set_holdings(symbol, -0.05)

    def on_securities_changed(self, changes: SecurityChanges) -> None:
        for removed in changes.removed_securities:
            self.liquidate(removed.symbol)
            self.deregister_indicator(removed.ema)

        for added in changes.added_securities:
            added.ema = self.ema(added.symbol, 50, Resolution.DAILY)
            self.warm_up_indicator(added.symbol, added.ema, Resolution.DAILY)
```