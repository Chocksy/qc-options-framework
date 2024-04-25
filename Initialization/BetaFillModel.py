#region imports
from AlgorithmImports import *
#endregion
import numpy as np


# Custom Fill model based on Beta distribution:
#  - Orders are filled based on a Beta distribution  skewed towards the mid-price with Sigma = bidAskSpread/6 (-> 99% fills within the bid-ask spread)
class BetaFillModel(ImmediateFillModel):

    # Initialize Random Number generator with a fixed seed (for replicability)
    random = np.random.RandomState(1234)

    def __init__(self, context):
        self.context = context

    def MarketFill(self, asset, order):
        # Start the timer
        self.context.executionTimer.start()

        # Get the random number generator
        random = BetaFillModel.random
        # Compute the Bid-Ask spread
        bidAskSpread = abs(asset.AskPrice - asset.BidPrice)
        # Compute the Mid-Price
        midPrice = 0.5 * (asset.AskPrice + asset.BidPrice)
        # Call the parent method
        fill = super().MarketFill(asset, order)
        # Setting the parameters of the Beta distribution:
        # - The shape parameters (alpha and beta) are chosen such that the fill is "reasonably close" to the mid-price about 96% of the times
        # - How close -> The fill price is within 15% of half the bid-Ask spread
        if order.Direction == OrderDirection.Sell:
            # Beta distribution in the range [Bid-Price, Mid-Price], skewed towards the Mid-Price
            # - Fill price is within the range [Mid-Price - 0.15*bidAskSpread/2, Mid-Price] with about 96% probability
            offset = asset.BidPrice
            alpha = 20
            beta = 1
        else:
            # Beta distribution in the range [Mid-Price, Ask-Price], skewed towards the Mid-Price
            # - Fill price is within the range [Mid-Price, Mid-Price + 0.15*bidAskSpread/2] with about 96% probability
            offset = midPrice
            alpha = 1
            beta = 20
        # Range (width) of the Beta distribution
        range = bidAskSpread / 2.0
        # Compute the new fillPrice (centered around the midPrice)
        fillPrice = round(offset + range * random.beta(alpha, beta), 2)
        # Update the FillPrice attribute
        fill.FillPrice = fillPrice
        # Stop the timer
        self.context.executionTimer.stop()
        # Return the fill
        return fill
