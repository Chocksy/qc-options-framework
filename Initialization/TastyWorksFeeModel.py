#region imports
from AlgorithmImports import *
#endregion


class TastyWorksFeeModel:
    def GetOrderFee(self, parameters):
        optionFee = min(10, parameters.Order.AbsoluteQuantity * 0.5)
        transactionFee = parameters.Order.AbsoluteQuantity * 0.14
        return OrderFee(CashAmount(optionFee + transactionFee, 'USD'))

