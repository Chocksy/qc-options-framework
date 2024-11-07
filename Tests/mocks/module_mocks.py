from unittest.mock import MagicMock
from .algorithm_imports import Resolution

class ToolsModuleMock:
    """Mock for the Tools module and its submodules"""
    @staticmethod
    def create_mocks():
        return {
            'Tools.Performance': MagicMock(),
            'Tools.DataHandler': MagicMock(),
            'Tools': MagicMock(Resolution=Resolution)
        }

class ModuleMocks:
    """Collection of all module-level mocks"""
    @staticmethod
    def get_all():
        return {
            **ToolsModuleMock.create_mocks(),
            # Add other module mocks here as needed
        } 