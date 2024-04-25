#region imports
from AlgorithmImports import *
#endregion


class AlwaysBuyingPowerModel(BuyingPowerModel):
    def __init__(self, context):
        super().__init__()
        self.context = context

    def HasSufficientBuyingPowerForOrder(self, parameters):
        # custom behavior: this model will assume that there is always enough buying power
        hasSufficientBuyingPowerForOrderResult = HasSufficientBuyingPowerForOrderResult(True)
        self.context.Log(f"CustomBuyingPowerModel: {hasSufficientBuyingPowerForOrderResult.IsSufficient}")

        return hasSufficientBuyingPowerForOrderResult
