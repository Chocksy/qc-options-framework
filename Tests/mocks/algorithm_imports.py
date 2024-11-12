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
    Call = "Call"
    Put = "Put"

class Market:
    USA = "USA"

class Symbol:
    @staticmethod
    def Create(symbol_str):
        mock = MagicMock()
        mock.Value = symbol_str
        return mock

    create_canonical_option = MagicMock()

    def __init__(self):
        pass

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
            symbol=MagicMock(
                ID=MagicMock(
                    StrikePrice=100.0,
                    Date=datetime.now() + timedelta(days=30)
                ),
                Value="TEST"
            )
        )
        # Pre-populate with TEST symbol
        self["TEST"] = self._default_security
    
    def __getitem__(self, key):
        # Handle both Symbol objects and strings
        if hasattr(key, 'Value'):
            key = key.Value
        if key not in self:
            self[key] = self._default_security
        return super().__getitem__(key)

class QCAlgorithm:
    def __init__(self):
        self.Securities = Securities()
        self.Portfolio = {}
        self.Time = datetime.now()
        self.StartDate = datetime.now() - timedelta(days=30)
        self.EndDate = datetime.now() + timedelta(days=30)
        self.logLevel = 0
        self.Resolution = Resolution
        self.Log = MagicMock()
        self.Plot = MagicMock()
        self.openPositions = MagicMock(Count=0)
        self.timeResolution = Resolution.Minute
        
        # Add mocked methods for DataHandler tests
        self.AddEquity = MagicMock()
        self.AddIndex = MagicMock()
        self.AddOption = MagicMock()
        self.AddIndexOption = MagicMock()
        self.AddOptionContract = MagicMock()
        self.AddIndexOptionContract = MagicMock()

    def GetLastKnownPrice(self, security):
        return MagicMock(Price=100.0)

    def AddChart(self, chart):
        pass

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
        
        # Add symbol property structure
        self.symbol = MagicMock()
        self.symbol.ID = MagicMock()
        self.symbol.ID.StrikePrice = self._strike
        self.symbol.ID.Date = self._expiry
        self.symbol.Value = "TEST"
        self.symbol.Underlying = self._underlying_symbol

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
    def OpenInterest(self) -> float:
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
    def __init__(self):
        pass

    def GetMaximumOrderQuantityForTargetBuyingPower(self, *args, **kwargs):
        return MagicMock(Quantity=100)

    def GetLeverage(self, *args, **kwargs):
        return 1.0

    def GetReservedBuyingPowerForPosition(self, *args, **kwargs):
        return 0.0

# Export all the mocks
__all__ = [
    'Resolution',
    'OptionRight',
    'Market',
    'Symbol',
    'QCAlgorithm',
    'Insight',
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
    'BuyingPowerModel'
] 