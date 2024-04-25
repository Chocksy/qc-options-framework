#region imports
from AlgorithmImports import *
#endregion

from .Base import Base

class SPXExecutionModel(Base):
    PARAMETERS = {
        # "orderAdjustmentPct": None,
        # The increment we are going to use to adjust the limit price. This is used to 
        # properly adjust the price for SPX options. If the limit price is 0.5 and this
        # value is 0.01 then we are going to try and fill the order at 0.51, 0.52, 0.53, etc.
        "adjustmentIncrement": 0.05,
        # Speed of fill. Option taken from https://optionalpha.com/blog/smartpricing-released. 
        # Can be: "Normal", "Fast", "Patient"
        # "Normal" will retry every 3 minutes, "Fast" every 1 minute, "Patient" every 5 minutes.
        "speedOfFill": "Fast",
        # maxRetries is the maximum number of retries we are going to do to try 
        # and get a fill. This is calculated based on the speedOfFill and this 
        # value is just for reference.
        "maxRetries": 10,
    }
    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context)