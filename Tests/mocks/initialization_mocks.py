from unittest.mock import MagicMock
from datetime import time
from .algorithm_imports import BuyingPowerModel

class InitializationModuleMock:
    """Mock for the Initialization module and its submodules"""
    @staticmethod
    def create_mocks():
        # Create AlwaysBuyingPowerModel mock
        always_buying_power_model = type('AlwaysBuyingPowerModel', (BuyingPowerModel,), {})
        
        mock_module = MagicMock()
        mock_module.AlwaysBuyingPowerModel = always_buying_power_model
        mock_module.SetupBaseStructure = SetupBaseStructureMock
        mock_module.BuyingPowerModel = BuyingPowerModel
        
        return {
            'Initialization': mock_module,
            'Initialization.AlwaysBuyingPowerModel': MagicMock(
                AlwaysBuyingPowerModel=always_buying_power_model,
                BuyingPowerModel=BuyingPowerModel
            ),
            'Initialization.SetupBaseStructure': MagicMock(
                SetupBaseStructure=SetupBaseStructureMock
            )
        } 

class SetupBaseStructureMock:
    """Mock of SetupBaseStructure class"""
    DEFAULT_PARAMETERS = {
        "creditStrategy": True,
        "riskFreeRate": 0.001,
        "portfolioMarginStress": 0.12,
        "emaMemory": 200,
        "backtestMarketCloseCutoffTime": time(15, 45, 0)
    }

    def __init__(self, context):
        self.context = context

    def Setup(self):
        return self

    def CompleteSecurityInitializer(self, security):
        pass

    def AddUnderlying(self, strategy, ticker):
        return self

    def checkOpenPositions(self):
        pass

    def AddConfiguration(self, **kwargs):
        pass 