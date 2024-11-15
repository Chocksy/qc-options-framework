from unittest.mock import MagicMock
import datetime as dt  # Import as dt to avoid naming conflicts
from dataclasses import dataclass, field
from typing import List, Union, Optional
from datetime import time  # Add this import

# Create datetime class with all needed components
datetime = dt.datetime
timedelta = dt.timedelta
date = dt.date

@dataclass
class Insight:
    """Mock of QuantConnect's Insight class"""
    Symbol: str = ""
    Type: str = "Price"
    Direction: str = "Up"
    Period: timedelta = timedelta(days=1)
    Magnitude: float = 0.0
    Confidence: float = 0.0
    SourceModel: str = "MockModel"
    Weight: float = 0.0

    @staticmethod
    def Price(symbol, period, direction):
        """Mock implementation of static Price method"""
        return Insight(
            Symbol=symbol,
            Period=period,
            Direction=direction
        )

class InsightDirection:
    """Mock of QuantConnect's InsightDirection enum"""
    Up = "Up"
    Down = "Down"
    Flat = "Flat"

@dataclass
class PortfolioTarget:
    """Mock of QuantConnect's PortfolioTarget class"""
    _symbol: Union[str, 'Symbol']
    _quantity: float
    _tag: str = ""
    minimum_order_margin_percentage_warning_sent: Optional[bool] = None

    @property
    def symbol(self) -> 'Symbol':
        return self._symbol if isinstance(self._symbol, Symbol) else Symbol.Create(self._symbol)

    @property
    def quantity(self) -> float:
        return self._quantity

    @property
    def tag(self) -> str:
        return self._tag

    @staticmethod
    def percent(algorithm: 'QCAlgorithm', 
                symbol: Union['Symbol', str], 
                percent: float,
                return_delta_quantity: bool = False,
                tag: str = "") -> 'PortfolioTarget':
        """Mock implementation of percent method"""
        # Simple mock implementation
        mock_quantity = 100.0 * percent  # Simplified calculation
        return PortfolioTarget(symbol, mock_quantity, tag)

    def __str__(self) -> str:
        return f"PortfolioTarget({self.symbol}, {self.quantity}, {self.tag})"

class Resolution:
    Minute = "Minute"
    Hour = "Hour"
    Daily = "Daily"

class OptionRight:
    """Mock of QuantConnect's OptionRight enum"""
    Call = "Call"
    Put = "Put"
    CALL = "Call"  # Add uppercase versions
    PUT = "Put"    # Add uppercase versions

    @staticmethod
    def create(right_str):
        """Helper method to create OptionRight from string"""
        right_str = right_str.lower()
        if right_str == "call":
            return OptionRight.Call
        elif right_str == "put":
            return OptionRight.Put
        return None

class Market:
    USA = "USA"

class Symbol:
    @staticmethod
    def Create(symbol_str):
        mock = MagicMock()
        mock.Value = symbol_str
        return mock

    @staticmethod
    def create_option(underlying_symbol, market, option_style, right, strike_price, expiry_date):
        """Mock implementation of create_option"""
        mock = MagicMock()
        mock.ID = MagicMock(
            underlying=MagicMock(symbol=underlying_symbol),
            market=market,
            option_style=option_style,
            option_right=right,
            strike_price=strike_price,
            date=expiry_date
        )
        mock.Value = f"{underlying_symbol}_{strike_price}_{right}_{expiry_date}"
        return mock

    @staticmethod
    def create_canonical_option(underlying_symbol, target_option, market=None, alias=None):
        """Mock implementation of create_canonical_option matching QC's implementation
        
        Args:
            underlying_symbol: The underlying symbol
            target_option: The target option ticker (e.g. SPXW)
            market: The market (defaults to underlying's market)
            alias: Optional alias for symbol cache
        """
        mock = MagicMock()
        mock.ID = MagicMock(
            underlying=MagicMock(symbol=underlying_symbol),
            market=market or Market.USA,
            option_style="European",  # Default for index options
            date=None
        )
        mock.Value = f"{target_option}_CANONICAL_{market or Market.USA}"
        mock.Underlying = underlying_symbol
        return mock

    def __init__(self):
        pass

    # Make create_canonical_option also available as a class attribute for testing
    create_canonical_option = MagicMock(side_effect=create_canonical_option.__func__)

class Security:
    """Mock of QuantConnect's Security class"""
    def __init__(self, symbol=None):
        self.Symbol = symbol or Symbol.Create("TEST")
        self.Type = SecurityType.Equity
        self.Price = 100.0
        self.BidPrice = 0.95
        self.AskPrice = 1.05
        self.Close = 100.0
        self.IsTradable = True
        self.HasData = True
        self.Holdings = MagicMock(Quantity=0)
        self.VolatilityModel = None
        self.Expiry = datetime.now() + timedelta(days=30)
        
        # Greeks for options
        self.delta = None
        self.gamma = None
        self.theta = None
        self.vega = None
        self.rho = None
        self.iv = None

    def SetDataNormalizationMode(self, mode):
        pass

    def SetMarketPrice(self, price):
        self.Price = price

    def SetBuyingPowerModel(self, model):
        pass

    def SetFillModel(self, model):
        pass

    def SetFeeModel(self, model):
        pass

    def SetOptionAssignmentModel(self, model):
        pass

    def PriceModel(self, model):
        pass

class SecurityType:
    """Mock of QuantConnect's SecurityType enum"""
    Equity = "Equity"
    Option = "Option"
    IndexOption = "IndexOption"
    Index = "Index"

class TradeBar:
    """Mock of QuantConnect's TradeBar class"""
    def __init__(self, time, symbol, open_price, high, low, close, volume):
        self.Time = time
        self.Symbol = symbol
        self.Open = open_price
        self.High = high
        self.Low = low
        self.Close = close
        self.Volume = volume
        self.Value = close  # Usually the closing price is used as the value
        self.Period = timedelta(minutes=1)  # Default period

    def Update(self, price, volume=0):
        self.Close = price
        self.Value = price
        self.Volume += volume

class DataNormalizationMode:
    """Mock of QuantConnect's DataNormalizationMode enum"""
    Raw = "Raw"
    Adjusted = "Adjusted"
    SplitAdjusted = "SplitAdjusted"
    TotalReturn = "TotalReturn"

class BrokerageName:
    """Mock of QuantConnect's BrokerageName enum"""
    InteractiveBrokersBrokerage = "InteractiveBrokersBrokerage"
    TradierBrokerage = "TradierBrokerage"
    OandaBrokerage = "OandaBrokerage"

class AccountType:
    """Mock of QuantConnect's AccountType enum"""
    Margin = "Margin"
    Cash = "Cash"

class Securities(dict):
    """Mock of QuantConnect's Securities dictionary"""
    def __init__(self):
        super().__init__()
        self._default_security = MagicMock(
            BidPrice=0.95,
            AskPrice=1.05,
            Price=100.0,
            Close=100.0,
            IsTradable=True,
            Volume=1000,
            OpenInterest=100,
            symbol=MagicMock(
                ID=MagicMock(
                    StrikePrice=100.0,
                    Date=datetime.now() + timedelta(days=30)
                ),
                Value="TEST"
            )
        )
        # Configure the MagicMock to return actual values
        type(self._default_security).Volume = property(lambda x: 1000)
        type(self._default_security).OpenInterest = property(lambda x: 100)
        
        # Pre-populate with TEST symbol
        self["TEST"] = self._default_security
    
    def items(self):
        """Return a list of items to allow safe iteration"""
        return list(super().items())
    
    def clear(self):
        """Clear all items including default security"""
        super().clear()

    def __getitem__(self, key):
        if hasattr(key, 'Value'):
            key = key.Value
        return super().__getitem__(key)

    def __delitem__(self, key):
        if hasattr(key, 'Value'):
            key = key.Value
        if key in self:
            super().__delitem__(key)

    def __contains__(self, key):
        if hasattr(key, 'Value'):
            key = key.Value
        return super().__contains__(key)

class QCAlgorithm:
    def __init__(self):
        self.Securities = Securities()
        self.Portfolio = MagicMock(
            SetPositions=MagicMock()
        )
        self.Time = datetime.now()
        self.StartDate = datetime.now() - timedelta(days=30)
        self.EndDate = datetime.now() + timedelta(days=30)
        self.logLevel = 0
        self.Resolution = Resolution
        self.Log = MagicMock()
        self.Plot = MagicMock()
        self.openPositions = MagicMock(Count=0)
        self.timeResolution = Resolution.Minute
        self.optionContractsSubscriptions = []
        
        # Add missing attributes
        self.universe_settings = MagicMock(resolution=None)
        self.LiveMode = False
        self.strategies = []
        self._benchmark = None  # Add private benchmark variable
        
        # Add mocked methods for DataHandler tests
        self.AddEquity = MagicMock()
        self.AddIndex = MagicMock()
        self.AddOption = MagicMock()
        self.AddIndexOption = MagicMock()
        self.AddOptionContract = MagicMock()
        self.AddIndexOptionContract = MagicMock()
        self.SetBrokerageModel = MagicMock()
        self.RemoveSecurity = MagicMock()
        
        # Add new attributes
        self.charting = MagicMock(updateStats=MagicMock())
        self.TradingCalendar = MagicMock()
        
        # Add new methods as MagicMocks
        self.SetBenchmark = MagicMock()

    @property
    def Benchmark(self):
        """Mock implementation of Benchmark property"""
        return self._benchmark

    def SetBenchmark(self, symbol):
        """Mock implementation of SetBenchmark"""
        self._benchmark = symbol

    def lastTradingDay(self, expiry):
        """Mock implementation of lastTradingDay"""
        if isinstance(expiry, datetime):
            return expiry.date()
        return expiry

    def GetLastKnownPrice(self, security):
        return MagicMock(Price=100.0)

    def AddChart(self, chart):
        pass

    def SetBrokerageModel(self, brokerage_name, account_type):
        """Mock implementation of SetBrokerageModel"""
        pass

    def RemoveSecurity(self, symbol):
        """Mock implementation of RemoveSecurity"""
        if symbol in self.Securities:
            del self.Securities[symbol]

class Greeks:
    """Mock of QuantConnect's Greeks class"""
    def __init__(self):
        self.delta = 0.0
        self.gamma = 0.0
        self.theta = 0.0
        self.vega = 0.0
        self.rho = 0.0

class OptionContract:
    """Mock of QuantConnect's OptionContract class"""
    def __init__(self, symbol=None, security=None):
        self._symbol = symbol or Symbol.Create("TEST")
        self._strike = 100.0
        self._expiry = datetime.now() + timedelta(days=30)
        self._right = OptionRight.Call
        self._greeks = Greeks()
        self._time = datetime.now()
        self._theoretical_price = 1.0
        self._implied_volatility = 0.2
        self._open_interest = 100
        self._last_price = 100.0
        self._volume = 1000
        self._bid_price = 0.95
        self._bid_size = 10
        self._ask_price = 1.05
        self._ask_size = 10
        self._underlying_last_price = 100.0
        self._underlying_symbol = "TEST"
        self._bsm_greeks = None  # Add BSM Greeks storage
        
        # Add symbol property structure
        self.symbol = MagicMock()
        self.symbol.ID = MagicMock()
        self.symbol.ID.StrikePrice = self._strike
        self.symbol.ID.Date = self._expiry
        self.symbol.Value = "TEST"
        self.symbol.Underlying = self._underlying_symbol

    @property
    def BSMGreeks(self):
        """Mock BSMGreeks property that persists"""
        if self._bsm_greeks is None:
            # Create a mock with Delta property that returns the stored delta
            self._bsm_greeks = MagicMock()
            self._bsm_greeks.Delta = self._greeks.delta
        return self._bsm_greeks

    @BSMGreeks.setter
    def BSMGreeks(self, value):
        """Allow setting BSMGreeks directly"""
        self._bsm_greeks = value

    # Properties with correct casing
    @property
    def greeks(self) -> Greeks:
        return self._greeks

    @property
    def implied_volatility(self) -> float:
        return self._implied_volatility

    # Keep other properties as they are...

    @property
    def Symbol(self) -> 'Symbol':
        return self.symbol

    @property
    def Strike(self) -> float:
        return self._strike

    @property
    def Expiry(self) -> datetime:
        return self._expiry

    @property
    def Right(self) -> 'OptionRight':
        return self._right

    @property
    def Time(self) -> datetime:
        return self._time

    @property
    def OpenInterest(self) -> int:
        return self._open_interest

    @property
    def Volume(self) -> int:
        return self._volume

    @property
    def BidPrice(self) -> float:
        return self._bid_price

    @property
    def AskPrice(self) -> float:
        return self._ask_price

    @property
    def Price(self) -> float:
        return self._last_price

    @property
    def UnderlyingSymbol(self) -> str:
        return self._underlying_symbol

    @property
    def UnderlyingLastPrice(self) -> float:
        return self._underlying_last_price

    @property
    def Underlying(self):
        """Returns the underlying symbol - this matches the actual implementation"""
        return self.symbol.Underlying

    def __str__(self) -> str:
        return f"OptionContract({self.Symbol}, {self.Strike}, {self.Expiry}, {self.Right})"

class OrderStatus:
    """Mock of QuantConnect's OrderStatus enum"""
    Invalid = "Invalid"
    CancelPending = "CancelPending"
    Canceled = "Canceled"
    Filled = "Filled"
    PartiallyFilled = "PartiallyFilled"
    Submitted = "Submitted"
    None_ = "None"

class SeriesType:
    Line = "Line"
    Scatter = "Scatter"
    Bar = "Bar"
    Candlestick = "Candlestick"

class Color:
    Red = "Red"
    Green = "Green"

class ScatterMarkerSymbol:
    Triangle = "Triangle"
    TriangleDown = "TriangleDown"

class Series:
    def __init__(self, name, series_type, unit, color=None, symbol=None):
        self.Name = name
        self.SeriesType = series_type
        self.Unit = unit
        self.Color = color
        self.Symbol = symbol

class CandlestickSeries(Series):
    def __init__(self, name, unit):
        super().__init__(name, SeriesType.Candlestick, unit)

class Chart:
    def __init__(self, name):
        self.Name = name
        self.Series = []

    def AddSeries(self, series):
        self.Series.append(series)

class BuyingPowerModel:
    """Mock of QuantConnect's BuyingPowerModel"""
    NULL = None
    
    def __init__(self):
        pass

    def GetMaximumOrderQuantityForTargetBuyingPower(self, *args, **kwargs):
        return MagicMock(Quantity=100)

    def GetLeverage(self, *args, **kwargs):
        return 1.0

    def GetReservedBuyingPowerForPosition(self, *args, **kwargs):
        return 0.0

class ImmediateFillModel:
    """Mock of QuantConnect's ImmediateFillModel"""
    def __init__(self):
        pass

    def MarketFill(self, order, security):
        return MagicMock(
            OrderEvent=MagicMock(
                OrderId=order.Id,
                Symbol=order.Symbol,
                Status=OrderStatus.Filled,
                FillPrice=security.Price,
                FillQuantity=order.Quantity
            )
        )

    def StopMarketFill(self, order, security):
        return self.MarketFill(order, security)

    def StopLimitFill(self, order, security):
        return self.MarketFill(order, security)

    def LimitFill(self, order, security):
        return self.MarketFill(order, security)

    def MarketOnCloseFill(self, order, security):
        return self.MarketFill(order, security)

    def MarketOnOpenFill(self, order, security):
        return self.MarketFill(order, security)

class SecurityPositionGroupModel:
    """Mock of QuantConnect's SecurityPositionGroupModel"""
    Null = None

class OptionPriceModels:
    """Mock of QuantConnect's OptionPriceModels"""
    @staticmethod
    def CrankNicolsonFD():
        return MagicMock()

class StandardDeviationOfReturnsVolatilityModel:
    """Mock of QuantConnect's StandardDeviationOfReturnsVolatilityModel"""
    def __init__(self, periods):
        self.periods = periods

    def Update(self, security, trade_bar):
        pass

# Export all the mocks
__all__ = [
    'Resolution',
    'OptionRight',
    'Market',
    'Symbol',
    'Security',
    'SecurityType',
    'TradeBar',
    'DataNormalizationMode',
    'BrokerageName',
    'AccountType',
    'QCAlgorithm',
    'Insight',
    'InsightDirection',
    'PortfolioTarget',
    'OptionContract',
    'datetime',
    'timedelta',
    'date',
    'time',
    'OrderStatus',
    'SeriesType',
    'Color',
    'ScatterMarkerSymbol',
    'Series',
    'CandlestickSeries',
    'Chart',
    'BuyingPowerModel',
    'ImmediateFillModel',
    'SecurityPositionGroupModel',
    'OptionPriceModels',
    'StandardDeviationOfReturnsVolatilityModel'
] 