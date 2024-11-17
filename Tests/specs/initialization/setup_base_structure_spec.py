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
            # Set current time on algorithm
            self.algorithm.Time = datetime.now()
            
            # Create a mock expired security
            expired_security = MagicMock(
                Type=SecurityType.Option,
                Symbol=MagicMock(Value='opt1'),
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
            
            # Add working orders setup with concrete datetime values
            current_time = datetime.now()
            self.mock_order = MagicMock(
                orderId='order1',
                orderType='open',
                limitOrderExpiryDttm=current_time + timedelta(minutes=5)
            )
            
            # Add position setup with concrete datetime values
            self.mock_position = MagicMock(
                orderTag='tag1',
                orderId='order1',
                legs=[MagicMock(expiry=current_time + timedelta(minutes=5))],
                cancelOrder=MagicMock()
            )
            
            # Configure position to return openOrder with concrete datetime
            mock_order = MagicMock(
                limitOrderExpiryDttm=current_time + timedelta(minutes=5)
            )
            self.mock_position.__getitem__.return_value = mock_order
            
            # Add to algorithm
            self.algorithm.workingOrders = {'tag1': self.mock_order}
            self.algorithm.allPositions = {'order1': self.mock_position}
            self.algorithm.openPositions = {'tag1': 'order1'}
            
            # Set includeCancelledOrders flag
            self.algorithm.includeCancelledOrders = True

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
            current_time = datetime.now()
            position.legs = [
                MagicMock(expiry=current_time - timedelta(days=1))
            ]
            # Configure position's order with concrete datetime
            mock_order = MagicMock(limitOrderExpiryDttm=current_time - timedelta(minutes=1))
            position.__getitem__ = MagicMock(return_value=mock_order)
            
            self.algorithm.allPositions = {'order1': position}
            self.algorithm.openPositions = {'tag1': 'order1'}
            
            self.setup.checkOpenPositions()
            
            expect(self.algorithm.openPositions).to(equal({}))

        with it('removes expired working orders due to time limit'):
            # Set order expiry to past time using concrete datetime
            current_time = datetime.now()
            self.mock_order.limitOrderExpiryDttm = current_time - timedelta(minutes=1)
            
            # Configure position's order with same expired datetime
            mock_expired_order = MagicMock(
                limitOrderExpiryDttm=current_time - timedelta(minutes=1)
            )
            self.mock_position.__getitem__.return_value = mock_expired_order
            
            self.setup.checkOpenPositions()
            
            expect(self.algorithm.workingOrders).to(equal({}))
            expect(self.mock_position.cancelOrder.called).to(be_true)
            expect('order1' in self.algorithm.allPositions).to(be_true)

        with it('removes expired working orders due to leg expiry'):
            # Set leg expiry to past time using concrete datetime
            current_time = datetime.now()
            self.mock_position.legs[0].expiry = current_time - timedelta(minutes=1)
            
            self.setup.checkOpenPositions()
            
            expect(self.algorithm.workingOrders).to(equal({}))
            expect(self.mock_position.cancelOrder.called).to(be_true)  # Using .called instead of call_count

        with it('removes cancelled positions when includeCancelledOrders is False'):
            self.algorithm.includeCancelledOrders = False
            
            # Set order expiry to past time
            self.mock_order.limitOrderExpiryDttm = datetime.now() - timedelta(minutes=1)
            
            # Configure position to return expired order for the specific order type
            mock_expired_order = MagicMock(
                limitOrderExpiryDttm=datetime.now() - timedelta(minutes=1)
            )
            def get_order(key):
                if key == 'openOrder':  # Match the orderType from mock_order
                    return mock_expired_order
                return MagicMock()
            self.mock_position.__getitem__.side_effect = get_order
            
            self.setup.checkOpenPositions()
            
            expect('order1' in self.algorithm.allPositions).to(be_false)
            expect(self.algorithm.workingOrders).to(equal({}))
            expect(self.algorithm.openPositions).to(equal({}))

        with it('keeps cancelled positions when includeCancelledOrders is True'):
            self.algorithm.includeCancelledOrders = True
            
            # Set order expiry to past time
            self.mock_order.limitOrderExpiryDttm = datetime.now() - timedelta(minutes=1)
            
            # Configure position to return expired order for the specific order type
            mock_expired_order = MagicMock(
                limitOrderExpiryDttm=datetime.now() - timedelta(minutes=1)
            )
            def get_order(key):
                if key == 'openOrder':  # Match the orderType from mock_order
                    return mock_expired_order
                return MagicMock()
            self.mock_position.__getitem__.side_effect = get_order
            
            self.setup.checkOpenPositions()
            
            expect('order1' in self.algorithm.allPositions).to(be_true)
            expect(self.algorithm.workingOrders).to(equal({}))
            expect(self.algorithm.openPositions).to(equal({}))

        with it('updates charting stats when removing expired positions'):
            self.mock_position.legs[0].expiry = datetime.now() - timedelta(minutes=1)
            
            self.setup.checkOpenPositions()
            
            self.algorithm.charting.updateStats.assert_called_with(self.mock_position)

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