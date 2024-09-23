# region imports
from AlgorithmImports import *
# endregion

import numpy as np
import pandas as pd
# The custom algo imports
from Execution import AutoExecutionModel, SmartPricingExecutionModel, SPXExecutionModel
from Monitor import HedgeRiskManagementModel, NoStopLossModel, StopLossModel, FPLMonitorModel, SPXicMonitor, CCMonitor, SPXButterflyMonitor, SPXCondorMonitor
from PortfolioConstruction import OptionsPortfolioConstruction
# The alpha models
from Alpha import FPLModel, CCModel, SPXic, SPXButterfly, SPXCondor, AssignmentModel
# The execution classes
from Initialization import SetupBaseStructure, HandleOrderEvents
from Tools import Performance


"""
Algorithm Structure Case v1:

1. We run the SetupBaseStructure.Setup() that will set the defaults for all the holders of data and base configuration
2. We have inside each AlphaModel a set of default parameters that will not be assigned to the context.
    - This means that each AlphaModel (Strategy) will have their own configuration defined in each class.
    - The AlphaModel will add the Underlying and options chains required
    - The QC algo will call the AlphaModel#Update method every 1 minute (self.timeResolution)
    - The Update method will call the AlphaModel#getOrder method
    - The getOrder method should use self.order (Alpha.Utils.Order) methods to get the options
    - The options returned will use the Alpha.Utils.Scanner and the Alpha.Utils.OrderBuilder classes
    - The final returned method requred to be returned by getOrder method is the Order#getOrderDetails
    - The Update method now in AlphaModel will use the getOrder method output to create Insights

"""

class CentralAlgorithm(QCAlgorithm):
    def Initialize(self):
        # WARNING!! If your are going to trade SPX 0DTE options then make sure you set the startDate after July 1st 2022.
        # This is the start of the data we have.
        self.SetStartDate(2023, 1, 3)
        self.SetEndDate(2023, 1, 17)
        # self.SetStartDate(2024, 4, 1)
        # self.SetEndDate(2024, 4, 30)
        # self.SetEndDate(2022, 9, 15)
        # Warmup for some days
        # self.SetWarmUp(timedelta(14))

        # Logging level:
        #  -> 0 = ERROR
        #  -> 1 = WARNING
        #  -> 2 = INFO
        #  -> 3 = DEBUG
        #  -> 4 = TRACE (Attention!! This can consume your entire daily log limit)
        self.logLevel = 0 if self.LiveMode else 3


        # Set the initial account value
        self.initialAccountValue = 100_000
        self.SetCash(self.initialAccountValue)

        # Time Resolution
        self.timeResolution = Resolution.Minute

        # Set Export method
        self.CSVExport = False
        # Should the trade log be displayed
        self.showTradeLog = False
        # Show the execution statistics
        self.showExecutionStats = False
        # Show the performance statistics
        self.showPerformanceStats = False

        # Set the algorithm base variables and structures
        self.structure = SetupBaseStructure(self).Setup()

        self.performance = Performance(self)

        # Set the algorithm framework models
        # self.SetAlpha(FPLModel(self))
        # self.SetAlpha(SPXic(self))
        # self.SetAlpha(CCModel(self))
        # self.SetAlpha(SPXButterfly(self))
        # self.SetAlpha(SPXCondor(self))
        self.SetAlpha(AssignmentModel(self))

        self.SetPortfolioConstruction(OptionsPortfolioConstruction(self))

        # self.SetPortfolioConstruction(InsightWeightingPortfolioConstructionModel())
        # self.SetExecution(SpreadExecutionModel())
        self.SetExecution(SPXExecutionModel(self))
        # self.SetExecution(AutoExecutionModel(self))
        # self.SetExecution(SmartPricingExecutionModel(self))
        # self.SetExecution(ImmediateExecutionModel())

        self.SetRiskManagement(NoStopLossModel(self))
        # self.SetRiskManagement(StopLossModel(self))
        # self.SetRiskManagement(FPLMonitorModel(self))
        # self.SetRiskManagement(SPXicMonitor(self))
        # self.SetRiskManagement(CCMonitor(self))
        # self.SetRiskManagement(SPXButterflyMonitor(self))
        # self.SetRiskManagement(SPXCondorMonitor(self))
        # self.SetRiskManagement(IBSMonitor(self))

    # Initialize the security every time that a new one is added
    def OnSecuritiesChanged(self, changes):
        for security in changes.AddedSecurities:
            self.structure.CompleteSecurityInitializer(security)
        for security in changes.RemovedSecurities:
            self.structure.ClearSecurity(security)

    def OnEndOfDay(self, symbol):
        self.structure.checkOpenPositions()
        self.performance.endOfDay(symbol)

    def OnOrderEvent(self, orderEvent):
        # Start the timer
        self.executionTimer.start()

        # Log the order event
        self.logger.debug(orderEvent)

        self.performance.OnOrderEvent(orderEvent)

        HandleOrderEvents(self, orderEvent).Call()
        # Loop through all strategies
        # for strategy in self.strategies:
        #     # Call the Strategy orderEvent handler
        #     strategy.handleOrderEvent(orderEvent)

        # Stop the timer
        self.executionTimer.stop()

    def OnEndOfAlgorithm(self) -> None:
        # Convert the dictionary into a Pandas Data Frame
        # dfAllPositions = pd.DataFrame.from_dict(self.allPositions, orient = "index")
        # Convert the dataclasses into Pandas Data Frame
        dfAllPositions = pd.json_normalize(obj.asdict() for k,obj in self.allPositions.items())

        if self.showExecutionStats:
            self.Log("")
            self.Log("---------------------------------")
            self.Log("     Execution  Statistics       ")
            self.Log("---------------------------------")
            self.executionTimer.showStats()
            self.Log("")
        if self.showPerformanceStats:
            self.Log("---------------------------------")
            self.Log("     Performance Statistics       ")
            self.Log("---------------------------------")
            self.performance.show()
            self.Log("")
            self.Log("")

        if self.showTradeLog:
            self.Log("---------------------------------")
            self.Log("           Trade Log             ")
            self.Log("---------------------------------")
            self.Log("")
            if self.CSVExport:
                # Print the csv header
                self.Log(dfAllPositions.head(0).to_csv(index = False, header = True, line_terminator = " "))
                # Print the data frame to the log in csv format (one row at a time to avoid QC truncation limitation)
                for i in range(0, len(dfAllPositions.index)):
                    self.Log(dfAllPositions.iloc[[i]].to_csv(index = False, header = False, line_terminator = " "))
            else:
                self.Log(f"\n#{dfAllPositions.to_string()}")
        self.Log("")

    def lastTradingDay(self, expiry):
        # Get the trading calendar
        tradingCalendar = self.TradingCalendar
        # Find the last trading day for the given expiration date
        lastDay = list(tradingCalendar.GetDaysByType(TradingDayType.BusinessDay, expiry - timedelta(days = 20), expiry))[-1].Date
        return lastDay




