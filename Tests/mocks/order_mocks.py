from dataclasses import dataclass, field
from datetime import datetime, timedelta
from unittest.mock import MagicMock

@dataclass
class MockOrder:
    """Mock for order objects used in testing order handlers"""
    orderType: str = "open"
    lastRetry: datetime = None
    _fillRetries: int = 1
    limitOrderPrice: float = 1.0
    
    @property
    def fillRetries(self):
        return self._fillRetries
        
    @fillRetries.setter
    def fillRetries(self, value):
        self._fillRetries = value

@dataclass
class MockExecOrder:
    """Mock for execution orders used in testing order handlers"""
    premium: float = 0.0
    fills: int = 0
    limitOrderExpiryDttm: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=1))
    limitOrderPrice: float = 0.0
    bidAskSpread: float = 0.1
    midPrice: float = 1.0
    midPriceMin: float = 0.0
    midPriceMax: float = 0.0
    limitPrice: float = 0.0
    fillPrice: float = 0.0
    openPremium: float = 0.0
    stalePrice: bool = False
    filled: bool = False
    maxLoss: float = 0.0
    transactionIds: list = field(default_factory=list)
    priceProgressList: list = field(default_factory=list)

def create_mock_contract(strike: float, side: int, symbol: str, underlying: str = "SPX"):
    """Helper to create consistently mocked option contracts"""
    contract = MagicMock()
    contract.Strike = strike
    contract.contractSide = side
    contract.Symbol = MagicMock()
    contract.Symbol.Value = symbol
    contract.Underlying = underlying
    return contract

def create_mock_leg(contract, side: int):
    """Helper to create consistently mocked option legs"""
    leg = MagicMock()
    leg.contract = contract
    leg.symbol = contract.Symbol
    leg.contractSide = side
    return leg 