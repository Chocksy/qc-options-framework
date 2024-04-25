#region imports
from AlgorithmImports import *
#endregion

import math
from datetime import datetime, timedelta

"""
The GoogleSheetsData class reads data from the Google Sheets CSV link directly during live mode. In backtesting mode, you can use a
static CSV file saved in the local directory with the same format as the Google Sheets file.

The format should be like this:
    datetime,type,put_strike,call_strike,minimum_premium
    2023-12-23 14:00:00,Iron Condor,300,350,0.50
    2023-12-24 14:00:00,Bear Call Spread,0,360,0.60
    2023-12-25 14:00:00,Bull Put Spread,310,0,0.70

Replace the google_sheet_csv_link variable in the GetSource method with your actual Google Sheets CSV link.

Example for alpha model:

    class MyAlphaModel(AlphaModel):

        def Update(self, algorithm, data):
            if not data.ContainsKey('SPY_TradeInstructions'):
                return []

            trade_instructions = data['SPY_TradeInstructions']

            if trade_instructions is None:
                return []

            # Check if the current time is past the instructed time
            if algorithm.Time < trade_instructions.Time:
                return []

            # Use the trade_instructions data to generate insights
            type = trade_instructions.Type
            call_strike = trade_instructions.CallStrike
            put_strike = trade_instructions.PutStrike
            minimum_premium = trade_instructions.MinimumPremium

            insights = []

            if type == "Iron Condor":
                insights.extend(self.GenerateIronCondorInsights(algorithm, call_strike, put_strike, minimum_premium))
            elif type == "Bear Call Spread":
                insights.extend(self.GenerateBearCallSpreadInsights(algorithm, call_strike, minimum_premium))
            elif type == "Bull Put Spread":
                insights.extend(self.GenerateBullPutSpreadInsights(algorithm, put_strike, minimum_premium))

            return insights
"""


class GoogleSheetsData(PythonData):
    def GetSource(self, config, date, isLiveMode):
        google_sheet_csv_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vS9oNUoYqY-u0WnLuJRCb8pSuQKcLStK8RaTfs5Cm9j6iiYNpx82iJuAc3D32zytXA4EiosfxjWKyJp/pub?gid=509927026&single=true&output=csv'
        if isLiveMode:
            return SubscriptionDataSource(google_sheet_csv_link, SubscriptionTransportMedium.Streaming)
        else:
            return SubscriptionDataSource(google_sheet_csv_link, SubscriptionTransportMedium.RemoteFile)
        
        # if isLiveMode:
        #     # Replace the link below with your Google Sheets CSV link
        #     google_sheet_csv_link = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vS9oNUoYqY-u0WnLuJRCb8pSuQKcLStK8RaTfs5Cm9j6iiYNpx82iJuAc3D32zytXA4EiosfxjWKyJp/pub?gid=509927026&single=true&output=csv'
        #     return SubscriptionDataSource(google_sheet_csv_link, SubscriptionTransportMedium.RemoteFile)

        # # In backtesting, you can use a static CSV file saved in the local directory
        # return SubscriptionDataSource("trade_instructions.csv", SubscriptionTransportMedium.LocalFile)

    def Reader(self, config, line, date, isLiveMode):
        if not line.strip():
            return None

        columns = line.split(',')

        if columns[0] == 'datetime':
            return None

        trade = GoogleSheetsData()
        trade.Symbol = config.Symbol
        trade.Value = float(columns[2]) or float(columns[3])

        # Parse the datetime and adjust the timezone
        trade_time = datetime.strptime(columns[0], "%Y-%m-%d %H:%M:%S") - timedelta(hours=7)

        # Round up the minute to the nearest 5 minutes
        minute = 5 * math.ceil(trade_time.minute / 5)
        # If the minute is 60, set it to 0 and add 1 hour
        if minute == 60:
            trade_time = trade_time.replace(minute=0, hour=trade_time.hour+1)
        else:
            trade_time = trade_time.replace(minute=minute)

        trade.Time = trade_time
        # trade.EndTime = trade.Time + timedelta(hours=4)
        trade["Type"] = columns[1]
        trade["PutStrike"] = float(columns[2])
        trade["CallStrike"] = float(columns[3])
        trade["MinimumPremium"] = float(columns[4])

        return trade
