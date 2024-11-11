from unittest.mock import MagicMock
from .algorithm_imports import Resolution, Chart, Series, SeriesType, Color, ScatterMarkerSymbol

class ToolsModuleMock:
    """Mock for the Tools module and its submodules"""
    @staticmethod
    def create_mocks():
        # Create ContractUtils mock that returns an instance
        contract_utils_instance = MagicMock()
        contract_utils_instance.bidAskSpread.return_value = 0.1
        contract_utils_instance.midPrice.return_value = 1.0
        
        contract_utils_class = MagicMock(return_value=contract_utils_instance)
        
        contract_utils_mock = MagicMock()
        contract_utils_mock.ContractUtils = contract_utils_class
        contract_utils_mock.Resolution = Resolution
        
        # Create DataHandler mock
        data_handler_mock = MagicMock()
        data_handler_mock.DataHandler = MagicMock
        data_handler_mock.Resolution = Resolution
        
        # Create Underlying mock
        underlying_mock = MagicMock()
        underlying_mock.Underlying = MagicMock
        underlying_mock.Resolution = Resolution

        # Create PositionsStore mock
        positions_store_mock = MagicMock()
        positions_store_mock.PositionsStore = MagicMock
        
        tools_mock = MagicMock(
            Resolution=Resolution,
            Chart=Chart,
            Series=Series,
            SeriesType=SeriesType,
            Color=Color,
            ScatterMarkerSymbol=ScatterMarkerSymbol,
            ContractUtils=contract_utils_class,  # Use the class that returns an instance
            Underlying=underlying_mock.Underlying,
            PositionsStore=positions_store_mock.PositionsStore,
            DataHandler=data_handler_mock.DataHandler
        )
        
        return {
            'Tools': tools_mock,
            'Tools.Performance': MagicMock(),
            'Tools.DataHandler': data_handler_mock,
            'Tools.Charting': MagicMock(),
            'Tools.ContractUtils': contract_utils_mock,
            'Tools.Underlying': underlying_mock,
            'Tools.Helper': MagicMock(),
            'Tools.Logger': MagicMock(),
            'Tools.PositionsStore': positions_store_mock,
            'AlgorithmImports': MagicMock(Resolution=Resolution)
        } 