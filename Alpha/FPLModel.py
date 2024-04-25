#region imports
from AlgorithmImports import *
#endregion

from .Base import Base
from Data.GoogleSheetsData import GoogleSheetsData

class FPLModel(Base):
    PARAMETERS = {
        # The start time at which the algorithm will start scheduling the strategy execution (to open new positions). No positions will be opened before this time
        "scheduleStartTime": time(9, 20, 0),
        # The stop time at which the algorithm will look to open a new position.
        "scheduleStopTime": None, # time(13, 0, 0),
        # Periodic interval with which the algorithm will check to open new positions
        "scheduleFrequency": timedelta(minutes = 5),
        # Maximum number of open positions at any given time
        "maxActivePositions": 2,
        # Days to Expiration
        "dte": 0,
        # The size of the window used to filter the option chain: options expiring in the range [dte-dteWindow, dte] will be selected
        "dteWindow": 0,
        "useLimitOrders": True,
        "limitOrderRelativePriceAdjustment": 0.2,
        "limitOrderAbsolutePrice": 0.5,
        "limitOrderExpiration": timedelta(hours=1),
        # Coarse filter for the Universe selection. It selects nStrikes on both sides of the ATM
        # strike for each available expiration
        # Example: 200 SPX @ 3820 & 3910C w delta @ 1.95 => 90/5 = 18
        "nStrikesLeft": 18,
        "nStrikesRight": 18,
        "maxOrderQuantity": 40,
        # Minimum premium accepted for opening a new position. Setting this to None disables it.
        "minPremium": 0.50,
        # Maximum premium accepted for opening a new position. Setting this to None disables it.
        "maxPremium": 1.5,
        "profitTarget": 0.5,
        "bidAskSpreadRatio": 0.4,
        "validateBidAskSpread": True,
        "marketCloseCutoffTime": None, #time(15, 45, 0),
        # "targetPremium": 500,
    }

    def __init__(self, context):
        # Call the Base class __init__ method
        super().__init__(context)
        # You can change the name here
        self.name = "FPLModel"
        self.nameTag = "FPL"
        self.ticker = "SPX"
        self.context.structure.AddUnderlying(self, self.ticker)
        self.customSymbol = self.context.AddData(GoogleSheetsData, "SPXT", Resolution.Minute).Symbol

    def getOrder(self, chain, data):
        if data.ContainsKey(self.customSymbol):
            self.logger.info(f'L: just got a new trade!! {data[self.customSymbol]}')
            print(f'P: just got a new trade!! {data[self.customSymbol]}')
            trade_instructions = data[self.customSymbol]
            tradeType = trade_instructions.Type
            condor = False
            self.logger.info(f'L: instructions: {trade_instructions}')
            print(f'P: instructions: {trade_instructions}')

            if tradeType == 'Call Credit Spreads':
                action = 'call'
                strike = trade_instructions.CallStrike 
            elif tradeType == 'Put Credit Spreads':
                action = 'put'
                strike = trade_instructions.PutStrike
            elif tradeType == 'Iron Condor':
                callStrike = trade_instructions.CallStrike 
                putStrike = trade_instructions.PutStrike
                condor = True
            else:
                return None

            if condor:
                return self.order.getIronCondorOrder(
                    chain, 
                    callStrike = callStrike, 
                    putStrike = putStrike, 
                    callWingSize = 5, 
                    putWingSize = 5
                )
            else:
                return self.order.getSpreadOrder(
                    chain,
                    action,
                    strike=strike,
                    wingSize=5,
                    sell=True
                )
        else:
            return None
        # if not chain.ContainsKey('SPXTRADES'):
        #     return []

        # customTrades = chain['SPXTRADES']

        # if customTrades is None:
        #     return []

        # # Check if the current time is past the instructed time
        # if self.context.Time < customTrades.Time:
        #     return []

        # # Use the customTrades data to generate insights
        # tradeType = customTrades.Type
        # call_strike = customTrades.CallStrike
        # put_strike = customTrades.PutStrike
        # minimum_premium = customTrades.MinimumPremium
        # self.Log(f'{data.EndTime}: Close: {data.Close}')
        # self.Plot(self.custom_data_symbol, 'Price', data.Close)

        #  strike = self.context.underlyingPrice() + self.parameters["distance"]
        