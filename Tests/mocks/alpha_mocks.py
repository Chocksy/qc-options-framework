from unittest.mock import MagicMock
from .algorithm_imports import BuyingPowerModel
from datetime import time, timedelta

class MockBase:
    """Mock of Alpha.Base class"""
    DEFAULT_PARAMETERS = {
        'targetProfit': 0.5,
        'slippage': 0.01,
        'validateBidAskSpread': False,
        'bidAskSpreadRatio': 0.25,
        'scheduleStartTime': time(9, 30, 0),
        'scheduleStopTime': None,
        'scheduleFrequency': timedelta(minutes=5),
        'minimumTradeScheduleDistance': timedelta(days=1),
        'checkForDuplicatePositions': True,
        'checkForOneDuplicateLeg': True,
        'maxActivePositions': 1,
        'maxOpenPositions': 2,
        'maxOrderQuantity': 1,
        'validateQuantity': True,
        'dte': 0,
        'dteWindow': 0,
        'dteThreshold': 21,
        'useFurthestExpiry': True,
        'dynamicDTESelection': False,
        'allowMultipleEntriesPerExpiry': False,
        'nStrikesLeft': 200,
        'nStrikesRight': 200,
        'forceDteThreshold': False,
        'ditThreshold': None,
        'hardDitThreshold': None,
        'forceDitThreshold': False,
        'slippage': 0.0,
        'bidAskSpreadRatio': 0.3,
        'validateBidAskSpread': False,
        'includeLegDetails': False,
        'legDatailsUpdateFrequency': 30,
        'trackLegDetails': False,
        'greeksIncluded': [],
        'computeGreeks': False,
        'marketCloseCutoffTime': time(15, 45, 0),
        'useLimitOrders': True,
        'limitOrderRelativePriceAdjustment': 0,
        'limitOrderExpiration': timedelta(hours=8),
        'limitOrderAbsolutePrice': None,
        'targetPremiumPct': None,
        'minPremium': None,
        'maxPremium': None,
        'targetPremium': None,
        'profitTargetMethod': "Premium",
        'profitTarget': 0.6,
        'thetaProfitDays': None,
        'delta': 10,
        'wingSize': 10,
        'putDelta': 10,
        'callDelta': 10,
        'netDelta': None,
        'putWingSize': 10,
        'callWingSize': 10,
        'butteflyType': None,
        'butterflyLeftWingSize': 10,
        'butterflyRightWingSize': 10,
        'useSlice': True,
    }

    @classmethod
    def getMergedParameters(cls):
        """Matches Base.py getMergedParameters"""
        return {**cls.DEFAULT_PARAMETERS, **getattr(cls, "PARAMETERS", {})}

    @classmethod
    def parameter(cls, key, default=0.0):
        """Matches Base.py parameter method"""
        return cls.getMergedParameters().get(key, default)

    def __str__(self):
        return self.name

class SPXic(MockBase):
    """Mock of actual SPXic strategy from Alpha folder"""
    name = "SPXic"  # Class attribute for consistent name access
    
    PARAMETERS = {
        'scheduleStartTime': None,
        'scheduleStopTime': None,
        'scheduleFrequency': None,
        'maxActivePositions': 10,
        'maxOpenPositions': 1,
        'allowMultipleEntriesPerExpiry': True,
        'minimumTradeScheduleDistance': None,
        'dte': 0,
        'dteWindow': 0,
        'useLimitOrders': True,
        'limitOrderRelativePriceAdjustment': 0.2,
        'limitOrderAbsolutePrice': 1.0,
        'limitOrderExpiration': None,
        'nStrikesLeft': 18,
        'nStrikesRight': 18,
        'targetPremiumPct': 0.01,
        'validateQuantity': False,
        'minPremium': 0.9,
        'maxPremium': 1.2,
        'profitTarget': 1.0,
        'bidAskSpreadRatio': 0.4,
        'validateBidAskSpread': True,
        'marketCloseCutoffTime': None,
        'putWingSize': 10,
        'callWingSize': 10,
    }

    def __init__(self, context=None):
        self.nameTag = "SPXic"
        self.ticker = "SPX"

class AlphaModuleMock:
    """Mock for the Alpha module and its submodules"""
    @staticmethod
    def create_mocks():
        # Create the strategy modules
        spxic_module = type('SPXicModule', (), {'SPXic': SPXic})
        
        # Create a mock for UnknownStrategy that has a proper string representation
        unknown_strategy_mock = MagicMock()
        unknown_strategy_mock.__str__ = lambda x: "UnknownStrategy"
        unknown_strategy_mock.name = "UnknownStrategy"
        
        unknown_module = type('UnknownModule', (), {'UnknownStrategy': unknown_strategy_mock})
        base_module = type('BaseModule', (), {'Base': MockBase})
        
        return {
            'Alpha': MagicMock(SPXic=SPXic, Base=MockBase),
            'Alpha.SPXic': spxic_module,
            'Alpha.UnknownStrategy': unknown_module,
            'Alpha.Base': base_module,
            'Alpha.FPLModel': MagicMock(),
            'Alpha.CCModel': MagicMock(),
            'Alpha.SPXButterfly': MagicMock(),
            'Alpha.SPXCondor': MagicMock(),
            'Alpha.AssignmentModel': MagicMock(),
            'Alpha.Utils': MagicMock(),
            'Alpha.Utils.Scanner': MagicMock(),
            'Alpha.Utils.Stats': MagicMock(),
        }