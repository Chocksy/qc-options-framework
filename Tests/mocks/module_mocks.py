from unittest.mock import MagicMock
from .algorithm_imports import Resolution, Chart, Series, SeriesType, Color, ScatterMarkerSymbol

class ToolsModuleMock:
    """Mock for the Tools module and its submodules"""
    @staticmethod
    def create_mocks():
        # Create ContractUtils mock
        contract_utils_mock = MagicMock()
        contract_utils_mock.ContractUtils = MagicMock
        
        # Create Underlying mock
        underlying_mock = MagicMock()
        underlying_mock.Underlying = MagicMock

        # Create PositionsStore mock
        positions_store_mock = MagicMock()
        positions_store_mock.PositionsStore = MagicMock
        
        return {
            'Tools.Performance': MagicMock(),
            'Tools.DataHandler': MagicMock(),
            'Tools.Charting': MagicMock(),
            'Tools.ContractUtils': contract_utils_mock,
            'Tools.Underlying': underlying_mock,
            'Tools.Helper': MagicMock(),
            'Tools.Logger': MagicMock(),
            'Tools.PositionsStore': positions_store_mock,
            'Tools': MagicMock(
                Resolution=Resolution,
                Chart=Chart,
                Series=Series,
                SeriesType=SeriesType,
                Color=Color,
                ScatterMarkerSymbol=ScatterMarkerSymbol,
                ContractUtils=contract_utils_mock.ContractUtils,
                Underlying=underlying_mock.Underlying,
                PositionsStore=positions_store_mock.PositionsStore
            )
        }

class ModuleMocks:
    """Collection of all module-level mocks"""
    @staticmethod
    def get_all():
        return {
            **ToolsModuleMock.create_mocks(),
            # Add other module mocks here as needed
        } 