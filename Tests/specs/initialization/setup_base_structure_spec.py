from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from datetime import datetime, timedelta, time

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Initialization.SetupBaseStructure import SetupBaseStructure
    from Tests.mocks.algorithm_imports import (
        SecurityType, DataNormalizationMode, BrokerageName, 
        AccountType, Resolution, OptionRight, Symbol,
        TradeBar, Chart, Series, Securities
    )

with description('SetupBaseStructure') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.setup = SetupBaseStructure(self.algorithm)
            
            # Mock common algorithm attributes
            self.algorithm.logger = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = {}
            self.algorithm.timeResolution = Resolution.Minute
            self.algorithm.SetSecurityInitializer = MagicMock()
            self.algorithm.Schedule = MagicMock()
            self.algorithm.DateRules = MagicMock()
            self.algorithm.TimeRules = MagicMock()

    with context('initialization'):
        with it('initializes with correct default parameters'):
            expect(self.setup.DEFAULT_PARAMETERS['creditStrategy']).to(be_true)
            expect(self.setup.DEFAULT_PARAMETERS['riskFreeRate']).to(equal(0.001))
            expect(self.setup.DEFAULT_PARAMETERS['portfolioMarginStress']).to(equal(0.12))
            expect(self.setup.DEFAULT_PARAMETERS['emaMemory']).to(equal(200))

    with context('Setup'):
        with it('configures basic algorithm components'):
            self.setup.Setup()
            
            # Verify basic initialization
            expect(self.algorithm.positions).to(equal({}))
            expect(hasattr(self.algorithm, 'logger')).to(be_true)
            expect(hasattr(self.algorithm, 'executionTimer')).to(be_true)
            expect(hasattr(self.algorithm, 'optionContractsSubscriptions')).to(be_true)
            expect(self.algorithm.optionContractsSubscriptions).to(equal([]))
            
            # Verify method calls
            self.algorithm.SetSecurityInitializer.assert_called_once()
            self.algorithm.Portfolio.SetPositions.assert_called_once()

    with context('CompleteSecurityInitializer'):
        with before.each:
            self.security = MagicMock()
            self.security.Type = SecurityType.Option
            self.security.Symbol = Factory.create_symbol()
            
        with it('initializes option securities correctly'):
            self.setup.CompleteSecurityInitializer(self.security)
            
            self.security.SetDataNormalizationMode.assert_called_with(DataNormalizationMode.Raw)
            self.security.SetMarketPrice.assert_called()
            self.security.SetFillModel.assert_called()
            self.security.SetFeeModel.assert_called()

        with it('initializes equity securities correctly'):
            self.security.Type = SecurityType.Equity
            self.security.VolatilityModel = MagicMock()
            
            # Mock history data
            history_data = MagicMock()
            history_data.empty = False
            history_data.columns = ['close']
            self.algorithm.History = MagicMock(return_value=history_data)
            
            self.setup.CompleteSecurityInitializer(self.security)
            
            self.security.SetDataNormalizationMode.assert_called_with(DataNormalizationMode.Raw)
            self.algorithm.History.assert_called()

    with context('AddUnderlying'):
        with before.each:
            self.strategy = MagicMock()
            self.strategy.ticker = "SPX"
            self.strategy.useSlice = False
            
        with it('adds underlying and options chain correctly'):
            self.setup.AddUnderlying(self.strategy, "SPX")
            
            expect(self.algorithm.strategies).to(contain(self.strategy))
            expect(self.strategy.ticker).to(equal("SPX"))
            self.algorithm.SetBenchmark.assert_called()
            
        with it('schedules market open events'):
            self.setup.AddUnderlying(self.strategy, "SPX")
            
            self.algorithm.Schedule.On.assert_called_once()
            
        with it('handles slice-based option chains'):
            self.strategy.useSlice = True
            self.setup.AddUnderlying(self.strategy, "SPX")
            
            expect(hasattr(self.strategy, 'optionSymbol')).to(be_true)

    with context('checkOpenPositions'):
        with before.each:
            # Create a mock expired security
            expired_security = MagicMock(
                Type=SecurityType.Option,
                Symbol=MagicMock(Value='opt1'),  # Make sure Symbol has Value attribute
                HasData=True,
                Expiry=datetime.now() - timedelta(days=1)
            )
            
            # Create a fresh Securities instance
            self.algorithm.Securities = Securities()
            self.algorithm.Securities.clear()  # Clear any default securities
            self.algorithm.Securities['opt1'] = expired_security
            
            # Mock RemoveSecurity to actually remove from Securities
            def remove_security(symbol):
                if hasattr(symbol, 'Value'):
                    key = symbol.Value
                else:
                    key = symbol
                if key in self.algorithm.Securities:
                    del self.algorithm.Securities[key]
            
            self.algorithm.RemoveSecurity = MagicMock(side_effect=remove_security)
            self.algorithm.openPositions = {}
            self.algorithm.workingOrders = {}
            self.algorithm.optionContractsSubscriptions = []  # Add this line
            
        with it('removes expired securities'):
            # Create a copy of the securities before checking positions
            initial_securities_count = len(self.algorithm.Securities)
            self.setup.checkOpenPositions()
            
            self.algorithm.logger.debug.assert_called()
            # Verify that ClearSecurity was called for expired options
            expect(len(self.algorithm.Securities)).to(equal(0))
            expect(initial_securities_count).to(equal(1))  # Verify we started with one security

        with it('handles expired positions'):
            position = MagicMock()
            position.legs = [
                MagicMock(expiry=datetime.now() - timedelta(days=1))
            ]
            self.algorithm.allPositions = {'order1': position}
            self.algorithm.openPositions = {'tag1': 'order1'}
            
            self.setup.checkOpenPositions()
            
            expect(self.algorithm.openPositions).to(equal({}))

    with context('AddConfiguration'):
        with it('adds configuration parameters correctly'):
            test_params = {
                'param1': 'value1',
                'param2': 'value2'
            }
            
            self.setup.AddConfiguration(**test_params)
            
            expect(hasattr(self.algorithm, 'param1')).to(be_true)
            expect(self.algorithm.param1).to(equal('value1'))
            expect(hasattr(self.algorithm, 'param2')).to(be_true)
            expect(self.algorithm.param2).to(equal('value2')) 