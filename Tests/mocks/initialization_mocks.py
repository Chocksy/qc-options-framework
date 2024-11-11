from unittest.mock import MagicMock
from .algorithm_imports import BuyingPowerModel

class InitializationModuleMock:
    """Mock for the Initialization module and its submodules"""
    @staticmethod
    def create_mocks():
        # Create AlwaysBuyingPowerModel mock
        always_buying_power_model = type('AlwaysBuyingPowerModel', (BuyingPowerModel,), {})
        
        mock_module = MagicMock()
        mock_module.AlwaysBuyingPowerModel = always_buying_power_model
        mock_module.SetupBaseStructure = MagicMock()
        mock_module.BuyingPowerModel = BuyingPowerModel
        
        return {
            'Initialization': mock_module,
            'Initialization.AlwaysBuyingPowerModel': MagicMock(
                AlwaysBuyingPowerModel=always_buying_power_model,
                BuyingPowerModel=BuyingPowerModel
            ),
            'Initialization.SetupBaseStructure': MagicMock()
        } 