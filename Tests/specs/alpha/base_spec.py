from mamba import description, context, it, before, after
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none, raise_error
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, time

# Import test helpers
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from Tests.mocks.alpha_mocks import MockBase

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Alpha.Base import Base
    from Alpha.Utils.Stats import Stats
    from Tests.mocks.algorithm_imports import (
        SecurityType, Resolution, OptionRight, Symbol,
        TradeBar, PortfolioTarget, datetime, timedelta,
        List, SecurityChanges, SecuritiesDict, AlphaModel,
        Slice
    )

with description('Alpha.Base') as self:
    with before.each:
        # Setup common test environment
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
            self.algorithm.IsWarmingUp = False
            self.algorithm.IsMarketOpen = MagicMock(return_value=True)
            
            # Mock structure
            self.algorithm.structure = MagicMock()
            self.algorithm.structure.AddConfiguration = MagicMock()
            
            # Create Stats instance
            self.stats = Stats()
            
            # Create Base instance
            self.base = Base(self.algorithm)
            self.base.stats = self.stats
            self.base.underlyingSymbol = "SPX"
            
            # Set required parameters from DEFAULT_PARAMETERS
            for key, value in MockBase.DEFAULT_PARAMETERS.items():
                setattr(self.base, key, value)

    with context('initialization'):
        with it('initializes with default parameters'):
            # Verify base attributes are set correctly
            expect(self.base.context).to(equal(self.algorithm))
            expect(self.base.name).to(equal('Base'))
            expect(self.base.nameTag).to(equal('Base'))
            
            # Verify default parameters were merged
            self.algorithm.structure.AddConfiguration.assert_called_once()
            call_kwargs = self.algorithm.structure.AddConfiguration.call_args.kwargs
            expect(call_kwargs).to(have_key('parent'))
            expect(call_kwargs).to(have_key('scheduleStartTime'))
            expect(call_kwargs).to(have_key('maxActivePositions'))

        with it('merges parameters correctly'):
            # Create a subclass with custom parameters
            class CustomBase(Base):
                PARAMETERS = {
                    'maxActivePositions': 5,
                    'customParam': 'test'
                }
            
            custom_base = CustomBase(self.algorithm)
            merged_params = custom_base.getMergedParameters()
            
            expect(merged_params['maxActivePositions']).to(equal(5))
            expect(merged_params['customParam']).to(equal('test'))
            expect(merged_params).to(have_key('scheduleStartTime'))  # From DEFAULT_PARAMETERS

        with it('retrieves parameters correctly'):
            param_value = self.base.parameter('maxActivePositions')
            expect(param_value).to(equal(1))  # Default value from DEFAULT_PARAMETERS
            
            # Test non-existent parameter with default
            param_value = self.base.parameter('nonexistent', 'default')
            expect(param_value).to(equal('default'))

    with context('update method'):
        with before.each:
            # Mock common attributes
            self.algorithm.logger = MagicMock(debug=MagicMock())
            self.algorithm.debug = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = SecuritiesDict()
            self.algorithm.Securities['SPX'] = MagicMock(Price=1.0)
            self.algorithm.Time = datetime.now()
            self.algorithm.openPositions = {}
            self.algorithm.allPositions = {}
            self.algorithm.workingOrders = {}
            self.algorithm.IsWarmingUp = False
            self.algorithm.IsMarketOpen = MagicMock(return_value=True)
            self.algorithm.dataHandler = MagicMock()
            self.algorithm.dataHandler.getOptionContracts = MagicMock(return_value=None)
            self.algorithm.performance = MagicMock()
            self.algorithm.performance.OnUpdate = MagicMock()
            
            # Mock structure
            self.algorithm.structure = MagicMock()
            self.algorithm.structure.AddConfiguration = MagicMock()
            self.algorithm.structure.checkOpenPositions = MagicMock()
            
            # Create Stats instance
            self.stats = Stats()
            
            # Create Base instance
            self.base = Base(self.algorithm)
            self.base.stats = self.stats
            self.base.underlyingSymbol = "SPX"
            self.base.last_trade_time = None
            
            # Set required parameters from DEFAULT_PARAMETERS
            for key, value in MockBase.DEFAULT_PARAMETERS.items():
                setattr(self.base, key, value)
                
            # Mock data
            self.mock_data = MagicMock()
            
            # Mock syncStats
            self.base.syncStats = MagicMock()

        with context('market conditions'):
            with it('skips processing during warmup'):
                self.algorithm.IsWarmingUp = True
                result = self.base.update(self.algorithm, MagicMock())
                expect(result).to(have_length(0))

            with it('skips processing when market closed'):
                self.algorithm.IsMarketOpen = MagicMock(return_value=False)
                result = self.base.update(self.algorithm, MagicMock())
                expect(result).to(have_length(0))

            with it('skips processing after cutoff time'):
                self.algorithm.Time = datetime.now().replace(hour=16, minute=1)
                result = self.base.update(self.algorithm, MagicMock())
                expect(result).to(have_length(0))

        with context('data processing'):
            with it('updates performance tracking'):
                self.base.update(self.algorithm, self.mock_data)
                self.algorithm.performance.OnUpdate.assert_called_once_with(self.mock_data)

            with it('synchronizes stats'):
                self.base.update(self.algorithm, self.mock_data)
                self.base.syncStats.assert_called_once()

            with it('checks open positions'):
                self.base.update(self.algorithm, self.mock_data)
                self.algorithm.structure.checkOpenPositions.assert_called_once()

    with context('duplicate checking'):
        with before.each:
            self.current_time = datetime.now()
            # Create mock contract symbols
            self.contract1 = MagicMock()
            self.contract1.Strike = 100
            self.contract1.Symbol = "SPX_100"
            
            self.contract2 = MagicMock()
            self.contract2.Strike = 105
            self.contract2.Symbol = "SPX_105"

            # Create proper order structure
            self.mock_order = {
                "expiry": self.current_time + timedelta(days=30),
                "strategyId": "test_strategy",
                "contracts": [self.contract1, self.contract2],
                "contractSide": {
                    "SPX_100": "Sell",
                    "SPX_105": "Buy"
                }
            }
            
            # Create proper position mock
            self.mock_position = MagicMock(
                expiryStr=(self.current_time + timedelta(days=30)).strftime("%Y-%m-%d"),
                strategyId="test_strategy",
                legs=[
                    MagicMock(strike=100, contractSide="Sell"),
                    MagicMock(strike=105, contractSide="Buy")
                ]
            )

        with it('detects duplicate legs correctly'):
            self.base.checkForDuplicatePositions = True
            self.algorithm.openPositions = {"tag1": "order1"}
            self.algorithm.allPositions = {"order1": self.mock_position}
            
            result = self.base.hasDuplicateLegs(self.mock_order)
            expect(result).to(be_true)

        with it('respects allowMultipleEntriesPerExpiry setting'):
            self.base.checkForDuplicatePositions = True
            self.base.allowMultipleEntriesPerExpiry = True
            self.algorithm.openPositions = {"tag1": "order1"}
            self.algorithm.allPositions = {"order1": self.mock_position}
            
            # Use a different expiry date
            self.mock_order["expiry"] = self.current_time + timedelta(days=60)
            
            result = self.base.hasDuplicateLegs(self.mock_order)
            expect(result).to(be_false)

        with it('handles single duplicate leg check'):
            self.base.checkForOneDuplicateLeg = True
            self.algorithm.openPositions = {"tag1": "order1"}
            self.algorithm.allPositions = {"order1": self.mock_position}
            
            result = self.base.hasOneDuplicateLeg(self.mock_order)
            expect(result).to(be_true)

    with context('CreateInsights'):
        with before.each:
            # Mock the order module
            self.base.order = MagicMock()
            self.base.order.updateChain = MagicMock()
            
            # Create a mock chain
            self.mock_chain = [
                MagicMock(Strike=100),
                MagicMock(Strike=105)
            ]
            
            # Create a mock position
            self.mock_position = MagicMock(
                orderId="order1",
                orderTag="tag1",
                insights=[MagicMock()]  # Mock insights
            )
            
            # Create a mock working order
            self.mock_working_order = MagicMock(
                orderId="order1",
                orderTag="tag1",
                insights=[MagicMock()],
                useLimitOrder=True,
                orderType="open"
            )
            
            # Setup order.buildOrderPosition to return our mocks
            self.base.order.buildOrderPosition = MagicMock(
                return_value=(self.mock_position, self.mock_working_order)
            )
            
            # Mock getOrder method that's normally implemented by child classes
            self.mock_order = {
                'strategyId': 'test_strategy',
                'strikes': [100, 105],
                'expiry': datetime.now() + timedelta(days=30),
                'contractSide': {
                    'SPX_100': 'Sell',
                    'SPX_105': 'Buy'
                },
                'contracts': self.mock_chain
            }
            self.base.getOrder = MagicMock(return_value=self.mock_order)

        with it('processes valid orders correctly'):
            insights = self.base.CreateInsights(self.mock_chain, None, MagicMock())
            
            # Verify chain was updated
            self.base.order.updateChain.assert_called_once_with(self.mock_chain)
            
            # Verify position was added to global dictionaries
            expect(self.algorithm.allPositions).to(have_key("order1"))
            expect(self.algorithm.openPositions).to(have_key("tag1"))
            expect(self.algorithm.workingOrders).to(have_key("tag1"))

        with it('handles None orders'):
            self.base.getOrder = MagicMock(return_value=None)
            insights = self.base.CreateInsights(self.mock_chain)
            expect(insights).to(have_length(0))

        with it('skips duplicate positions'):
            # Setup duplicate detection - need to mock both checks
            self.base.hasDuplicateLegs = MagicMock(return_value=True)
            self.base.hasOneDuplicateLeg = MagicMock(return_value=True)
            
            insights = self.base.CreateInsights(self.mock_chain)
            expect(insights).to(have_length(0))

        with it('handles multiple orders'):
            # Create multiple mock orders
            mock_orders = [
                {
                    'strategyId': 'test_strategy1',
                    'strikes': [100, 105],
                    'expiry': datetime.now() + timedelta(days=30),
                    'contractSide': {
                        'SPX_100': 'Sell',
                        'SPX_105': 'Buy'
                    },
                    'contracts': self.mock_chain
                },
                {
                    'strategyId': 'test_strategy2',
                    'strikes': [110, 115],
                    'expiry': datetime.now() + timedelta(days=30),
                    'contractSide': {
                        'SPX_110': 'Sell',
                        'SPX_115': 'Buy'
                    },
                    'contracts': self.mock_chain
                }
            ]
            
            # Setup getOrder to return multiple orders
            self.base.getOrder = MagicMock(return_value=mock_orders)
            
            insights = self.base.CreateInsights(self.mock_chain)
            
            # Verify multiple positions were created
            expect(self.base.order.buildOrderPosition.call_count).to(equal(2))
            expect(insights).to(have_length(2))  # Assuming each order generates one insight

        with it('handles failed position building'):
            # Setup buildOrderPosition to return None
            self.base.order.buildOrderPosition = MagicMock(return_value=(None, None))
            insights = self.base.CreateInsights(self.mock_chain)
            expect(insights).to(have_length(0)) 

    with context('syncStats'):
        with before.each:
            # Create a mock Security with proper price methods
            self.mock_security = MagicMock()
            self.mock_security.Price = 100.0
            self.mock_security.Close = 100.0
            
            # Add SPX to Securities dictionary
            self.algorithm.Securities["SPX"] = self.mock_security
            
            # Create a proper Underlying mock that matches the actual class
            class MockUnderlying:
                def __init__(self, context, underlyingSymbol):
                    self.context = context
                    self.underlyingSymbol = underlyingSymbol
                    self._price = 100.0
                    self._close = 100.0
                
                def Price(self):
                    return self._price
                
                def Close(self):
                    return self._close
                
                def set_prices(self, price, close):
                    self._price = price
                    self._close = close
            
            # Store the original Underlying class
            self.original_underlying = getattr(self.base, 'Underlying', None)
            # Replace with our mock
            self.base.Underlying = MockUnderlying
            
            # Reset stats before each test
            self.base.stats.currentDay = None
            self.base.stats.underlyingPriceAtOpen = None
            self.base.stats.highOfTheDay = None
            self.base.stats.lowOfTheDay = None
            self.base.stats.touchedEMAs = {}
            self.base.stats.hasOptions = None

        with after.each:
            # Restore the original Underlying class if it existed
            if self.original_underlying is not None:
                self.base.Underlying = self.original_underlying

        with it('initializes stats on first run'):
            self.algorithm.Time = datetime.now().replace(minute=5)  # Make sure we're on schedule
            self.base.syncStats()
            
            expect(self.base.stats.currentDay).to(equal(self.algorithm.Time.date()))
            expect(self.base.stats.underlyingPriceAtOpen).to(equal(100.0))
            expect(self.base.stats.highOfTheDay).to(equal(100.0))
            expect(self.base.stats.lowOfTheDay).to(equal(100.0))
            expect(self.base.stats.touchedEMAs).to(equal({}))

        with it('updates high/low prices during the day'):
            # Initialize first
            self.algorithm.Time = datetime.now().replace(minute=5)  # Make sure we're on schedule
            self.base.syncStats()
            
            # Change price and update again
            self.mock_security.Price = 110.0
            self.mock_security.Close = 110.0
            self.algorithm.Time = datetime.now().replace(minute=10)  # Make sure we're on schedule
            self.base.syncStats()
            
            expect(self.base.stats.highOfTheDay).to(equal(110.0))
            expect(self.base.stats.lowOfTheDay).to(equal(100.0))
            
            # Test low price update
            self.mock_security.Price = 90.0
            self.mock_security.Close = 90.0
            self.algorithm.Time = datetime.now().replace(minute=15)  # Make sure we're on schedule
            self.base.syncStats()
            
            expect(self.base.stats.highOfTheDay).to(equal(110.0))
            expect(self.base.stats.lowOfTheDay).to(equal(90.0))

        with it('resets stats on day change'):
            # Initialize first day
            self.base.syncStats()
            
            # Update high/low
            self.mock_security.Price = 110.0
            self.mock_security.Close = 110.0
            self.algorithm.Time = datetime.now().replace(minute=5)  # Make sure we're on schedule
            self.base.syncStats()
            
            # Change day
            next_day = self.algorithm.Time + timedelta(days=1)
            self.algorithm.Time = next_day.replace(minute=5)  # Make sure we're on schedule
            
            # Reset underlying price for new day
            self.mock_security.Price = 100.0
            self.mock_security.Close = 100.0
            self.base.syncStats()
            
            expect(self.base.stats.currentDay).to(equal(next_day.date()))
            expect(self.base.stats.underlyingPriceAtOpen).to(equal(100.0))
            expect(self.base.stats.highOfTheDay).to(equal(100.0))
            expect(self.base.stats.lowOfTheDay).to(equal(100.0))
            expect(self.base.stats.hasOptions).to(be_none)

        with it('updates charting data on schedule'):
            # Set time to match frequency
            self.algorithm.Time = datetime.now().replace(minute=5)
            self.algorithm.charting = MagicMock()
            
            self.base.syncStats()
            
            self.algorithm.charting.updateCharts.assert_called_once_with(
                symbol=self.base.underlyingSymbol
            ) 

    with context('market checks'):
        with it('detects market closed during warmup'):
            self.algorithm.IsWarmingUp = True
            expect(self.base.isMarketClosed()).to(be_true)
            
        with it('detects closed market'):
            self.algorithm.IsMarketOpen.return_value = False
            expect(self.base.isMarketClosed()).to(be_true)
            
        with it('detects open market'):
            self.algorithm.IsWarmingUp = False
            self.algorithm.IsMarketOpen.return_value = True
            expect(self.base.isMarketClosed()).to(be_false)

    with context('market schedule checks'):
        with before.each:
            self.base.context.Time = datetime.now().replace(hour=10, minute=0)
            self.base.last_trade_time = None
            self.base.scheduleStartTime = time(9, 30)
            self.base.scheduleStopTime = time(16, 0)
            
        with it('allows trading within schedule window'):
            expect(self.base.check_market_schedule()).to(be_true)
            
        with it('prevents trading before start time'):
            self.base.context.Time = datetime.now().replace(hour=9, minute=0)
            expect(self.base.check_market_schedule()).to(be_false)
            
        with it('prevents trading after stop time'):
            self.base.context.Time = datetime.now().replace(hour=16, minute=30)
            expect(self.base.check_market_schedule()).to(be_false)
            
        with it('respects minimum trade distance'):
            self.base.last_trade_time = self.base.context.Time - timedelta(minutes=30)
            self.base.minimumTradeScheduleDistance = timedelta(hours=1)
            expect(self.base.check_market_schedule()).to(be_false)
            
            self.base.last_trade_time = self.base.context.Time - timedelta(hours=2)
            expect(self.base.check_market_schedule()).to(be_true) 