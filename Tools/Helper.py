#region imports
from AlgorithmImports import *
#endregion


class Helper:
    def findIn(self, data, condition):
        return next((v for v in data if condition(v)), None)
