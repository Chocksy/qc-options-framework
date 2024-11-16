from unittest.mock import MagicMock
from datetime import datetime, timedelta
from Tests.spec_helper import patch_imports
from Tests.mocks.algorithm_imports import Symbol, Market, Resolution, QCAlgorithm

class Factory:
    @staticmethod
    def create_algorithm():
        algorithm = QCAlgorithm()
        
        # Add basic mocked methods
        algorithm.AddEquity = MagicMock()
        algorithm.AddIndex = MagicMock()
        algorithm.AddOption = MagicMock()
        algorithm.AddIndexOption = MagicMock()
        algorithm.AddOptionContract = MagicMock()
        algorithm.AddIndexOptionContract = MagicMock()
        algorithm.SetBrokerageModel = MagicMock()
        algorithm.RemoveSecurity = MagicMock()
        
        # Add required properties for BSM calculations
        algorithm.riskFreeRate = 0.01
        algorithm.portfolioMarginStress = 0.12
        algorithm.emaMemory = 200
        algorithm.backtestMarketCloseCutoffTime = None
        algorithm.logLevel = 0
        
        # Add performance tracking
        algorithm.performance = MagicMock(OnUpdate=MagicMock())
        
        # Add charting capabilities
        algorithm.charting = MagicMock(updateStats=MagicMock())
        
        # Add trading calendar
        algorithm.TradingCalendar = MagicMock()
        
        return algorithm

    @staticmethod
    def create_symbol(symbol_str="TEST"):
        """Creates a mock Symbol with proper string representation"""
        mock_symbol = MagicMock()
        mock_symbol.Value = symbol_str
        mock_symbol.__str__ = lambda x: symbol_str
        mock_symbol.__repr__ = lambda x: f"Symbol({symbol_str})"
        return mock_symbol

    @staticmethod
    def create_option_contract():
        """Creates a mock option contract with proper property values"""
        from Tests.mocks.algorithm_imports import OptionContract
        contract = OptionContract()
        return contract