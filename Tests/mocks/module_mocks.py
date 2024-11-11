from unittest.mock import MagicMock
from .tools_mocks import ToolsModuleMock
from .alpha_mocks import AlphaModuleMock
from .initialization_mocks import InitializationModuleMock

class ModuleMocks:
    """Collection of all module-level mocks"""
    @staticmethod
    def get_all():
        # Create mock modules
        tools_mocks = ToolsModuleMock.create_mocks()
        alpha_mocks = AlphaModuleMock.create_mocks()
        init_mocks = InitializationModuleMock.create_mocks()
        
        # Combine all mocks
        all_mocks = {
            **tools_mocks,
            **alpha_mocks,
            **init_mocks,
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