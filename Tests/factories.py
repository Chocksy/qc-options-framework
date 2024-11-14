from unittest.mock import MagicMock
from datetime import datetime, timedelta
from Tests.spec_helper import patch_imports

class Factory:
    @staticmethod
    def create_algorithm():
        with patch_imports()[0], patch_imports()[1]:
            from AlgorithmImports import QCAlgorithm
            return QCAlgorithm()

    @staticmethod
    def create_symbol(symbol_str="TEST"):
        with patch_imports()[0], patch_imports()[1]:
            from AlgorithmImports import Symbol
            return Symbol.Create(symbol_str)

    @staticmethod
    def create_option_contract():
        """Creates a mock option contract with proper property values"""
        from Tests.mocks.algorithm_imports import OptionContract
        contract = OptionContract()
        return contract