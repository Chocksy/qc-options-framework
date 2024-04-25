#region imports
from AlgorithmImports import *
#endregion


# Custom class: fills orders at the mid-price
class MidPriceFillModel(ImmediateFillModel):
    def __init__(self, context):
        self.context = context

    def MarketFill(self, asset, order):
        # Start the timer
        self.context.executionTimer.start()

        # Call the parent method
        fill = super().MarketFill(asset, order)
        # Compute the new fillPrice (at the mid-price)
        fillPrice = round(0.5 * (asset.AskPrice + asset.BidPrice), 2)
        # Update the FillPrice attribute
        fill.FillPrice = fillPrice
        # Stop the timer
        self.context.executionTimer.stop()
        # Return the fill
        return fill
