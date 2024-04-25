#region imports
from AlgorithmImports import *
#endregion

from Tools import Underlying

class Charting:
    def __init__(self, context, openPositions=True, Stats=True, PnL=True, WinLossStats=True, Performance=True, LossDetails=True, totalSecurities=False, Trades=True, Distribution=True):
        self.context = context

        self.resample = datetime.min

        # QUANTCONNECT limitations in terms of charts
        # Tier	            Max Series	Max Data Points per Series
        # Free	            10	        4,000
        # Quant Researcher	10	        8,000
        # Team	            25	        16,000
        # Trading Firm	    25	        32,000
        # Institution	    100	        96,000
        # Max datapoints set to 4000 (free), 8000 (researcher), 16000 (team) (the maximum allowed by QC)
        self.resamplePeriod = (context.EndDate - context.StartDate) / 8_000
        # Max number of series allowed
        self.maxSeries = 10

        self.charts = []

        # Create an object to store all the stats
        self.stats = CustomObject()

        # Store the details about which charts will be plotted (there is a maximum of 10 series per backtest)
        self.stats.plot = CustomObject()
        self.stats.plot.openPositions = openPositions
        self.stats.plot.Stats = Stats
        self.stats.plot.PnL = PnL
        self.stats.plot.WinLossStats = WinLossStats
        self.stats.plot.Performance = Performance
        self.stats.plot.LossDetails = LossDetails
        self.stats.plot.totalSecurities = totalSecurities
        self.stats.plot.Trades = Trades
        self.stats.plot.Distribution = Distribution

        # Initialize performance metrics
        self.stats.won = 0
        self.stats.lost = 0
        self.stats.winRate = 0.0
        self.stats.premiumCaptureRate = 0.0
        self.stats.totalCredit = 0.0
        self.stats.totalDebit = 0.0
        self.stats.PnL = 0.0
        self.stats.totalWinAmt = 0.0
        self.stats.totalLossAmt = 0.0
        self.stats.averageWinAmt = 0.0
        self.stats.averageLossAmt = 0.0
        self.stats.maxWin = 0.0
        self.stats.maxLoss = 0.0
        self.stats.testedCall = 0
        self.stats.testedPut = 0

        totalSecurities = Chart("Total Securities")
        totalSecurities.AddSeries(Series('Total Securities', SeriesType.Line, 0))

        # Setup Charts
        if openPositions:
            activePositionsPlot = Chart('Open Positions')
            activePositionsPlot.AddSeries(Series('Open Positions', SeriesType.Line, ''))
            self.charts.append(activePositionsPlot)

        if Stats:
            statsPlot = Chart('Stats')
            statsPlot.AddSeries(Series('Won', SeriesType.Line, '', Color.Green))
            statsPlot.AddSeries(Series('Lost', SeriesType.Line, '', Color.Red))
            self.charts.append(statsPlot)

        if PnL:
            pnlPlot = Chart('Profit and Loss')
            pnlPlot.AddSeries(Series('PnL', SeriesType.Line, ''))
            self.charts.append(pnlPlot)

        if WinLossStats:
            winLossStatsPlot = Chart('Win and Loss Stats')
            winLossStatsPlot.AddSeries(Series('Average Win', SeriesType.Line, '$', Color.Green))
            winLossStatsPlot.AddSeries(Series('Average Loss', SeriesType.Line, '$', Color.Red))
            self.charts.append(winLossStatsPlot)

        if Performance:
            performancePlot = Chart('Performance')
            performancePlot.AddSeries(Series('Win Rate', SeriesType.Line, '%'))
            performancePlot.AddSeries(Series('Premium Capture', SeriesType.Line, '%'))
            self.charts.append(performancePlot)

        # Loss Details chart. Only relevant in case of credit strategies
        if LossDetails:
            lossPlot = Chart('Loss Details')
            lossPlot.AddSeries(Series('Short Put Tested', SeriesType.Line, ''))
            lossPlot.AddSeries(Series('Short Call Tested', SeriesType.Line, ''))
            self.charts.append(lossPlot)

        if Trades:
            tradesPlot = Chart('Trades')
            tradesPlot.AddSeries(CandlestickSeries('UNDERLYING', '$'))
            tradesPlot.AddSeries(Series("OPEN TRADE", SeriesType.Scatter, "", Color.Green, ScatterMarkerSymbol.Triangle))
            tradesPlot.AddSeries(Series("CLOSE TRADE", SeriesType.Scatter, "", Color.Red, ScatterMarkerSymbol.TriangleDown))
            self.charts.append(tradesPlot)

        if Distribution:
            distributionPlot = Chart('Distribution')
            distributionPlot.AddSeries(Series('Distribution', SeriesType.Bar, ''))
            self.charts.append(distributionPlot)

        # Add the charts to the context
        for chart in self.charts:
            self.context.AddChart(chart)

        # TODO: consider this for strategies.
        # Call the chart initialization method of each strategy (give a chance to setup custom charts)
        # for strategy in self.strategies:
        #     strategy.setupCharts()

        # Add the first data point to the charts
        self.updateCharts()

    def updateUnderlying(self, bar):
        # Add the latest data point to the underlying chart
        # self.context.Plot("UNDERLYING", "UNDERLYING", bar)
        self.context.Plot("Trades", "UNDERLYING", bar)

    def updateCharts(self, symbol=None):
        # Start the timer
        self.context.executionTimer.start()

        # TODO: consider this for strategies.
        # Call the updateCharts method of each strategy (give a chance to update any custom charts)
        # for strategy in self.strategies:
        #     strategy.updateCharts()

        # Exit if there is nothing to update
        if self.context.Time.time() >= time(15, 59, 0):
            return
        
        # self.context.logger.info(f"Time: {self.context.Time}, Resample: {self.resample}")
        # In order to not exceed the maximum number of datapoints, we resample the charts.
        if self.context.Time <= self.resample: return

        self.resample = self.context.Time  + self.resamplePeriod

        plotInfo = self.stats.plot
        
        if plotInfo.Trades:
            # If symbol is defined then we print the symbol data on the chart
            if symbol is not None:
                underlying = Underlying(self.context, symbol)
                self.context.Plot("Trades", "UNDERLYING", underlying.Security().GetLastData())

        if plotInfo.totalSecurities:
            self.context.Plot("Total Securities", "Total Securities", self.context.Securities.Count)
        # Add the latest stats to the plots
        if plotInfo.openPositions:
            self.context.Plot("Open Positions", "Open Positions", self.context.openPositions.Count)
        if plotInfo.Stats:
            self.context.Plot("Stats", "Won", self.stats.won)
            self.context.Plot("Stats", "Lost", self.stats.lost)
        if plotInfo.PnL:
            self.context.Plot("Profit and Loss", "PnL", self.stats.PnL)
        if plotInfo.WinLossStats:
            self.context.Plot("Win and Loss Stats", "Average Win", self.stats.averageWinAmt)
            self.context.Plot("Win and Loss Stats", "Average Loss", self.stats.averageLossAmt)
        if plotInfo.Performance:
            self.context.Plot("Performance", "Win Rate", self.stats.winRate)
            self.context.Plot("Performance", "Premium Capture", self.stats.premiumCaptureRate)
        if plotInfo.LossDetails:
            self.context.Plot("Loss Details", "Short Put Tested", self.stats.testedPut)
            self.context.Plot("Loss Details", "Short Call Tested", self.stats.testedCall)
        if plotInfo.Distribution:
            self.context.Plot("Distribution", "Distribution", 0)

        # Stop the timer
        self.context.executionTimer.stop()

    def plotTrade(self, trade, orderType):
        # Start the timer
        self.context.executionTimer.start()

        # Add the trade to the chart
        strikes = []
        for leg in trade.legs:
            if trade.isCreditStrategy:
                if leg.isSold:
                    strikes.append(leg.strike)
            else:
                if leg.isBought:
                    strikes.append(leg.strike)
        # self.context.logger.info(f"plotTrades!! : Strikes: {strikes}")
        if orderType == "open":
            for strike in strikes:
                self.context.Plot("Trades", "OPEN TRADE", strike)
        else:
            for strike in strikes:
                self.context.Plot("Trades", "CLOSE TRADE", strike)
        
        # NOTE: this can not be made because there is a limit of 10 Series on all charts so it will fail!
        # for strike in strikes:
        #     self.context.Plot("Trades", f"TRADE {strike}", strike)

        # Stop the timer
        self.context.executionTimer.stop()

    def updateStats(self, closedPosition):
        # Start the timer
        self.context.executionTimer.start()

        orderId = closedPosition.orderId
        # Get the position P&L
        positionPnL = closedPosition.PnL
        # Get the price of the underlying at the time of closing the position
        priceAtClose = closedPosition.underlyingPriceAtClose

        if closedPosition.isCreditStrategy:
            # Update total credit (the position was opened for a credit)
            self.stats.totalCredit += closedPosition.openPremium
            # Update total debit (the position was closed for a debit)
            self.stats.totalDebit += closedPosition.closePremium
        else:
            # Update total credit (the position was closed for a credit)
            self.stats.totalCredit += closedPosition.closePremium
            # Update total debit (the position was opened for a debit)
            self.stats.totalDebit += closedPosition.openPremium

        # Update the total P&L
        self.stats.PnL += positionPnL
        # Update Win/Loss counters
        if positionPnL > 0:
            self.stats.won += 1
            self.stats.totalWinAmt += positionPnL
            self.stats.maxWin = max(self.stats.maxWin, positionPnL)
            self.stats.averageWinAmt = self.stats.totalWinAmt / self.stats.won
        else:
            self.stats.lost += 1
            self.stats.totalLossAmt += positionPnL
            self.stats.maxLoss = min(self.stats.maxLoss, positionPnL)
            self.stats.averageLossAmt = -self.stats.totalLossAmt / self.stats.lost

            # Check if this is a Credit Strategy
            if closedPosition.isCreditStrategy:
                # Get the strikes for the sold contracts
                sold_puts = [leg.strike for leg in closedPosition.legs if leg.isSold and leg.isPut]
                sold_calls = [leg.strike for leg in closedPosition.legs if leg.isSold and leg.isCall]

                if sold_puts and sold_calls:
                    # Get the short put and short call strikes
                    shortPutStrike = min(sold_puts)
                    shortCallStrike = max(sold_calls)

                    # Check if the short Put is in the money
                    if priceAtClose <= shortPutStrike:
                        self.stats.testedPut += 1
                    # Check if the short Call is in the money
                    elif priceAtClose >= shortCallStrike:
                        self.stats.testedCall += 1
                    # Check if the short Put is being tested
                    elif (priceAtClose-shortPutStrike) < (shortCallStrike - priceAtClose):
                        self.stats.testedPut += 1
                    # The short Call is being tested
                    else:
                        self.stats.testedCall += 1

        # Update the Win Rate
        if ((self.stats.won + self.stats.lost) > 0):
            self.stats.winRate = 100*self.stats.won/(self.stats.won + self.stats.lost)

        if self.stats.totalCredit > 0:
            self.stats.premiumCaptureRate = 100*self.stats.PnL/self.stats.totalCredit

        # Trigger an update of the charts
        self.updateCharts()
        self.plotTrade(closedPosition, "close")

        # Stop the timer
        self.context.executionTimer.stop()


# Dummy class useful to create empty objects
class CustomObject:
    pass


