#region imports
from AlgorithmImports import *
#endregion
import matplotlib.pyplot as plt
import mplfinance
import numpy as np
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

# Your New Python File
class Charting:
    def __init__(self, data, symbol = None):
        self.data = data
        self.symbol = symbol

    def plot(self):
        mplfinance.plot(self.data,
                type='candle',
                style='charles',
                title=f'{self.symbol.Value if self.symbol else "General"} OHLC',
                ylabel='Price ($)',
                figratio=(15, 10))