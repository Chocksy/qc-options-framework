from datetime import datetime, timedelta
from .mocks.algorithm_imports import QCAlgorithm, Symbol, OptionRight, OptionContract

class Factory:
    @staticmethod
    def create_algorithm():
        return QCAlgorithm()

    @staticmethod
    def create_symbol(ticker="TEST", security_type="Equity"):
        return Symbol.Create(ticker)

    @staticmethod
    def create_option_contract(symbol=None, right=OptionRight.Call, strike=100.0, expiry=None):
        contract = OptionContract(symbol)
        contract._right = right
        contract._strike = strike
        if expiry:
            contract._expiry = expiry
        return contract