from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_above
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from datetime import datetime, timedelta

with patch_imports()[0], patch_imports()[1]:
    from Tools.Charting import Charting
    from AlgorithmImports import Chart, Series, SeriesType, Resolution, Color, ScatterMarkerSymbol

with description('Charting') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.algorithm.AddChart = MagicMock()
            self.start_date = datetime(2024, 1, 1)
            self.end_date = datetime(2024, 12, 31)
            self.algorithm.StartDate = self.start_date
            self.algorithm.EndDate = self.end_date
            self.algorithm.Time = self.start_date
            self.algorithm.executionTimer = MagicMock()

    with context('initialization'):
        with it('creates default charts when all options are True'):
            charting = Charting(self.algorithm)
            expected_charts = ['Open Positions', 'Stats', 'Profit and Loss', 
                             'Win and Loss Stats', 'Performance', 'Loss Details',
                             'Trades', 'Distribution']
            
            # Verify AddChart was called for each expected chart
            calls = self.algorithm.AddChart.call_args_list
            expect(len(calls)).to(equal(len(expected_charts)))
            
            # Verify chart names
            chart_names = [call.args[0].Name for call in calls]
            for name in expected_charts:
                expect(chart_names).to(contain(name))

        with it('creates only specified charts when some options are False'):
            charting = Charting(self.algorithm, openPositions=False, Stats=False)
            
            # Verify specific charts were not created
            calls = self.algorithm.AddChart.call_args_list
            chart_names = [call.args[0].Name for call in calls]
            expect(chart_names).not_to(contain('Open Positions'))
            expect(chart_names).not_to(contain('Stats'))

    with context('updateCharts'):
        with before.each:
            self.charting = Charting(self.algorithm)
            self.algorithm.Plot = MagicMock()
            # Set Time to be after resample period to ensure charts are updated
            self.algorithm.Time = self.start_date + timedelta(days=2)  # Move time forward
            # Reset the mock counts after initialization
            self.algorithm.executionTimer.start.reset_mock()
            self.algorithm.executionTimer.stop.reset_mock()

        with it('updates all enabled charts'):
            self.charting.updateCharts()
            
            # Verify Plot was called for each enabled chart
            calls = self.algorithm.Plot.call_args_list
            expect(len(calls)).to(be_above(0))
            
            # Verify timer was used exactly once after initialization
            self.algorithm.executionTimer.start.assert_called_once()
            self.algorithm.executionTimer.stop.assert_called_once()

        with it('does not update charts before resample period'):
            # Set time back to start to test resampling logic
            self.algorithm.Time = self.start_date
            self.charting.updateCharts()
            
            # Verify Plot was not called
            calls = self.algorithm.Plot.call_args_list
            expect(len(calls)).to(equal(0))

    with context('plotTrade'):
        with before.each:
            self.charting = Charting(self.algorithm)
            self.algorithm.Plot = MagicMock()

        with it('plots open trades correctly'):
            mock_trade = MagicMock()
            mock_trade.legs = [
                MagicMock(isSold=True, strike=100, isBought=False),
                MagicMock(isSold=False, strike=105, isBought=True)
            ]
            mock_trade.isCreditStrategy = True
            
            self.charting.plotTrade(mock_trade, "open")
            
            # Verify Plot was called with correct parameters
            self.algorithm.Plot.assert_called_with("Trades", "OPEN TRADE", 100)

    with context('updateStats'):
        with before.each:
            self.charting = Charting(self.algorithm)
            self.algorithm.Plot = MagicMock()

        with it('updates statistics for winning trade'):
            mock_position = MagicMock(
                orderId="123",
                PnL=100,
                underlyingPriceAtClose=150,
                isCreditStrategy=True,
                openPremium=50,
                closePremium=25,
                legs=[]
            )
            
            self.charting.updateStats(mock_position)
            
            expect(self.charting.stats.won).to(equal(1))
            expect(self.charting.stats.lost).to(equal(0))
            expect(self.charting.stats.PnL).to(equal(100))
            expect(self.charting.stats.winRate).to(equal(100))

        with it('updates statistics for losing trade'):
            mock_position = MagicMock(
                orderId="123",
                PnL=-100,
                underlyingPriceAtClose=150,
                isCreditStrategy=True,
                openPremium=50,
                closePremium=75,
                legs=[
                    MagicMock(isSold=True, strike=145, isPut=True, isCall=False),
                    MagicMock(isSold=True, strike=155, isPut=False, isCall=True)
                ]
            )
            
            self.charting.updateStats(mock_position)
            
            expect(self.charting.stats.won).to(equal(0))
            expect(self.charting.stats.lost).to(equal(1))
            expect(self.charting.stats.PnL).to(equal(-100))
            expect(self.charting.stats.winRate).to(equal(0)) 