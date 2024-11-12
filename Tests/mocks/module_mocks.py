from unittest.mock import MagicMock
from .tools_mocks import ToolsModuleMock
from .alpha_mocks import AlphaModuleMock
from .initialization_mocks import InitializationModuleMock
from .algorithm_imports import (
    Resolution, Symbol, Market, Insight, PortfolioTarget, 
    datetime, timedelta, OptionContract
)
import sys

class ModuleMocks:
    """Collection of all module-level mocks"""
    @staticmethod
    def get_all():
        # Create mock AlgorithmImports module
        mock_algo_imports = MagicMock()
        mock_algo_imports.Resolution = Resolution
        mock_algo_imports.Symbol = Symbol
        mock_algo_imports.Market = Market
        mock_algo_imports.Insight = Insight
        mock_algo_imports.PortfolioTarget = PortfolioTarget
        mock_algo_imports.datetime = datetime
        mock_algo_imports.timedelta = timedelta
        mock_algo_imports.OptionContract = OptionContract

        # Add to sys.modules
        sys.modules['AlgorithmImports'] = mock_algo_imports
        sys.modules['Tools.AlgorithmImports'] = mock_algo_imports
        
        # Create mock modules
        tools_mocks = ToolsModuleMock.create_mocks()
        alpha_mocks = AlphaModuleMock.create_mocks()
        init_mocks = InitializationModuleMock.create_mocks()
        
        # Combine all mocks
        all_mocks = {
            **tools_mocks,
            **alpha_mocks,
            **init_mocks,
            'AlgorithmImports': mock_algo_imports,
        }
        
        # Create a mock for UnknownStrategy that has a proper string representation
        strategy_mock = MagicMock()
        strategy_mock.__str__ = lambda x: "UnknownStrategy"
        strategy_mock.name = "UnknownStrategy"
        
        # Set up the UnknownStrategy mock
        unknown_module = MagicMock()
        unknown_module.UnknownStrategy = strategy_mock
        all_mocks['Alpha.UnknownStrategy'] = unknown_module
        
        return all_mocks

    @staticmethod
    def cleanup():
        # Clean up sys.modules entries
        if 'AlgorithmImports' in sys.modules:
            del sys.modules['AlgorithmImports']
        if 'Tools.AlgorithmImports' in sys.modules:
            del sys.modules['Tools.AlgorithmImports']