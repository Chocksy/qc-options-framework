from unittest.mock import MagicMock
from .algorithm_imports import Resolution, Chart, Series, SeriesType, Color, ScatterMarkerSymbol
from datetime import datetime

class DataHandlerMock:
    def __init__(self, context, ticker, strategy):
        self.context = context
        self.ticker = ticker
        self.strategy = strategy
        self.Resolution = Resolution

class MockObjectStore:
    def __init__(self):
        self.stored_data = {}
        self.saved_data = {}

    def save(self, key, data):
        self.saved_data[key] = data

    def read(self, key):
        return self.stored_data.get(key)

class MockContext:
    def __init__(self):
        self.allPositions = {}
        self.openPositions = {}
        self.Time = datetime.now()
        self.object_store = None
        self.logger = MockLogger()

    def debug(self, message):
        self.logger.debug(message)

class MockLogger:
    def error(self, message):
        pass

    def warning(self, message):
        pass

    def debug(self, message):
        pass

class ToolsModuleMock:
    """Mock for the Tools module and its submodules"""
    @staticmethod
    def create_mocks():
        # Create ContractUtils mock that returns an instance
        contract_utils_instance = MagicMock()
        contract_utils_instance.bidAskSpread.return_value = 0.1
        contract_utils_instance.midPrice.return_value = 1.0
        
        contract_utils_class = MagicMock(return_value=contract_utils_instance)
        
        # Create mock for Tools.DataHandler with Resolution
        data_handler_mock = MagicMock()
        data_handler_mock.DataHandler = DataHandlerMock
        data_handler_mock.Resolution = Resolution
        
        # Create mock for Tools with Resolution
        tools_mock = MagicMock(
            Resolution=Resolution,
            Chart=Chart,
            Series=Series,
            SeriesType=SeriesType,
            Color=Color,
            ScatterMarkerSymbol=ScatterMarkerSymbol,
            ContractUtils=contract_utils_class,
            DataHandler=DataHandlerMock
        )

        return {
            'Tools': tools_mock,
            'Tools.Performance': MagicMock(),
            'Tools.DataHandler': data_handler_mock,
            'Tools.Charting': MagicMock(),
            'Tools.ContractUtils': MagicMock(Resolution=Resolution),
            'Tools.Underlying': MagicMock(Resolution=Resolution),
            'Tools.Helper': MagicMock(),
            'Tools.Logger': MagicMock(),
            'Tools.PositionsStore': MagicMock(),
            'Tools.ProviderOptionContract': MagicMock(),
            'AlgorithmImports': MagicMock(Resolution=Resolution)
        }