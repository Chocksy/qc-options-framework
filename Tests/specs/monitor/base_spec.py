from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from datetime import datetime, timedelta, time

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Monitor.Base import Base
    from Tests.mocks.algorithm_imports import (
        SecurityType, Resolution, OptionRight, Symbol,
        TradeBar, PortfolioTarget, datetime, timedelta,
        RiskManagementModel, List, SecurityChanges, SecuritiesDict
    )
    from Initialization.SetupBaseStructure import SetupBaseStructure

with description('Monitor.Base') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Mock common attributes
            self.algorithm.logger = MagicMock(debug=MagicMock())
            self.algorithm.debug = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = SecuritiesDict()
            self.algorithm.Time = datetime.now()
            self.algorithm.openPositions = {}
            self.algorithm.allPositions = {}
            self.algorithm.workingOrders = {}
            self.algorithm.strategyMonitors = {}
            
            # Add backtest cutoff attributes
            self.algorithm.EndDate = datetime.now() + timedelta(days=30)
            self.algorithm.lastTradingDay = MagicMock(return_value=datetime.now().date())
            self.algorithm.backtestMarketCloseCutoffTime = time(15, 45, 0)
            self.algorithm.endOfBacktestCutoffDttm = datetime.combine(
                self.algorithm.lastTradingDay(self.algorithm.EndDate),
                self.algorithm.backtestMarketCloseCutoffTime
            )
            
            # Add structure attribute with proper AddConfiguration behavior
            def mock_add_configuration(parent=None, **kwargs):
                target = parent if parent is not None else self.algorithm
                for key, value in kwargs.items():
                    setattr(target, key, value)
                    
            self.algorithm.structure = MagicMock()
            self.algorithm.structure.AddConfiguration = MagicMock(side_effect=mock_add_configuration)
            
            # Create the Base instance
            self.monitor = Base(self.algorithm)

    with context('initialization'):
        with it('initializes with correct default parameters'):
            # Verify AddConfiguration was called with correct parameters
            self.algorithm.structure.AddConfiguration.assert_called_once()
            
            # Get the parameters that were passed to AddConfiguration
            call_kwargs = self.algorithm.structure.AddConfiguration.call_args.kwargs
            
            # Verify parent was passed
            expect(call_kwargs['parent']).to(equal(self.monitor))
            
            # Check that parameters were set on the monitor instance
            expect(self.monitor.managePositionFrequency).to(equal(1))
            expect(self.monitor.profitTarget).to(equal(0.8))
            expect(self.monitor.stopLossMultiplier).to(equal(1.9))
            expect(self.monitor.capStopLoss).to(be_true)

    with context('ManageRisk'):
        with before.each:
            # Create mock position
            self.mock_position = MagicMock()
            self.mock_position.orderId = "order1"
            self.mock_position.orderTag = "tag1"
            self.mock_position.openOrder = MagicMock(
                filled=True,
                premium=1.0,
                maxLoss=-5.0
            )
            # Set concrete values for profit checking - set to values that won't trigger closes
            self.mock_position.positionPnL = -0.5  # Not enough for stop loss, not profitable
            self.mock_position.targetProfit = 0.8
            self.mock_position.orderQuantity = 1
            
            # Create proper leg mock with concrete orderSide value
            leg_mock = MagicMock()
            leg_mock.orderSide = 0  # Set to 0 to prevent closing
            leg_mock.symbol = MagicMock()
            self.mock_position.legs = [leg_mock]
            
            self.mock_position.strategy = MagicMock()
            self.mock_position.orderMidPrice = 1.0
            self.mock_position.priceProgressList = []
            self.mock_position.updatePnLRange = MagicMock()
            self.mock_position.closeOrder = MagicMock()
            
            # Mock strategyParam to return values that won't trigger closes
            def mock_strategy_param(param_name):
                param_values = {
                    'dte': 30,
                    'ditThreshold': None,  # No DIT threshold
                    'dteThreshold': None,  # No DTE threshold
                    'forceDitThreshold': False,
                    'forceDteThreshold': False,
                    'hardDitThreshold': None,
                    'marketCloseCutoffTime': None,
                    'limitOrderExpiration': timedelta(minutes=5),
                    'useLimitOrders': True
                }
                return param_values.get(param_name)
            self.mock_position.strategyParam = MagicMock(side_effect=mock_strategy_param)
            
            # Add position to algorithm
            self.algorithm.openPositions = {"tag1": "order1"}
            self.algorithm.allPositions = {"order1": self.mock_position}
            
            # Configure mock position's getPositionValue to set positionPnL
            def mock_get_position_value(context):
                pass  # Keep the positionPnL at -0.5
            self.mock_position.getPositionValue = MagicMock(side_effect=mock_get_position_value)
            
            # Set up strategy monitor
            self.algorithm.strategyMonitors['Base'] = self.monitor
            
            # Mock expiry and other date-related methods - set to dates that won't trigger closes
            current_time = datetime.now()
            self.mock_position.expiry = current_time + timedelta(days=30)
            self.mock_position.openFilledDttm = current_time - timedelta(days=1)  # Recent position
            self.mock_position.expiryLastTradingDay = MagicMock(return_value=current_time + timedelta(days=29))
            self.mock_position.expiryMarketCloseCutoffDttm = MagicMock(return_value=None)
            
        with it('skips management when not on schedule'):
            self.algorithm.Time = datetime.now().replace(minute=2)  # Not divisible by managePositionFrequency
            result = self.monitor.ManageRisk(self.algorithm, [])
            expect(result).to(have_length(0))
            
        with it('processes positions on schedule'):
            self.algorithm.Time = datetime.now().replace(minute=5)  # Divisible by managePositionFrequency
            result = self.monitor.ManageRisk(self.algorithm, [])
            self.mock_position.getPositionValue.assert_called_once()

    with context('checkStopLoss'):
        with before.each:
            self.position = MagicMock()
            self.position.openOrder = MagicMock(
                premium=1.0,
                maxLoss=-5.0
            )
            self.position.orderQuantity = 1
            self.position.positionPnL = 0.0
            self.position.orderMidPrice = 1.0
            self.position.priceProgressList = []
            
            # Set stopLossMultiplier and capStopLoss on the algorithm context
            self.algorithm.stopLossMultiplier = 1.9
            self.algorithm.capStopLoss = True
            
        with it('returns True when stop loss is hit'):
            self.position.positionPnL = -2.0  # Greater than stopLoss threshold
            result = self.monitor.checkStopLoss(self.position)
            expect(result).to(be_true)
            
        with it('returns False when position is profitable'):
            self.position.positionPnL = 0.5
            result = self.monitor.checkStopLoss(self.position)
            expect(result).to(be_false)

    with context('checkProfitTarget'):
        with before.each:
            self.position = MagicMock()
            self.position.openOrder = MagicMock(premium=1.0)
            self.position.positionPnL = 0.0
            self.position.targetProfit = None
            
            # Set profitTarget on the algorithm context
            self.algorithm.profitTarget = 0.8
            
        with it('returns True when profit target is hit'):
            self.position.positionPnL = 0.9  # Above profitTarget threshold
            result = self.monitor.checkProfitTarget(self.position)
            expect(result).to(be_true)
            
        with it('returns False when below profit target'):
            self.position.positionPnL = 0.5
            result = self.monitor.checkProfitTarget(self.position)
            expect(result).to(be_false)

    with context('closePosition'):
        with before.each:
            self.position = MagicMock()
            self.position.orderId = "order1"
            self.position.orderTag = "tag1"
            self.position.legs = [
                MagicMock(symbol="SPX", orderSide=1)
            ]
            self.position.strategyParam = MagicMock(return_value=timedelta(minutes=5))
            self.position.expiryLastTradingDay = MagicMock(return_value=datetime.now() + timedelta(days=1))
            self.position.expiryMarketCloseCutoffDttm = MagicMock(return_value=None)
            self.position.closeOrder = MagicMock()
            self.position.underlyingSymbol = MagicMock(return_value="SPX")
            
            # Add position to algorithm's openPositions
            self.algorithm.openPositions = {"tag1": "order1"}
            self.algorithm.allPositions = {"order1": self.position}
            
            # Add security to Securities dictionary
            mock_security = MagicMock()
            mock_security.Close = 100.0
            self.algorithm.Securities["SPX"] = mock_security
            
        with it('creates correct portfolio targets'):
            result = self.monitor.closePosition(self.position, ["Test Close"], stopLossFlg=False)
            expect(result).to(have_length(1))
            expect(self.algorithm.workingOrders).to(have_key("tag1"))
            
            # Verify the working order was created correctly
            working_order = self.algorithm.workingOrders["tag1"]
            expect(working_order.orderId).to(equal("order1"))
            expect(working_order.useLimitOrder).to(be_true)
            expect(working_order.orderType).to(equal("close")) 