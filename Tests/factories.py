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
        """Creates a mock option contract with consistent expiry dates"""
        with patch_imports()[0], patch_imports()[1]:
            from AlgorithmImports import OptionContract
            
            # Create a fixed expiry date for consistency
            expiry_date = datetime.now() + timedelta(days=30)
            
            contract = OptionContract()
            contract._expiry = expiry_date
            contract.symbol.ID.Date = expiry_date  # Make sure both dates match
            
            return contract