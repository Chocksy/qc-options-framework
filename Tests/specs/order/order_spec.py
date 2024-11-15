from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, time
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Order.Order import Order
    from Tests.mocks.algorithm_imports import (
        OrderStatus, Symbol, TradeBar, datetime, timedelta,
        Insight, InsightDirection, PortfolioTarget, OptionRight,
        OptionContract
    )

with description('Order') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Fix the strategy mock setup
            self.strategy = MagicMock()
            self.strategy.name = "TestStrategy"
            self.strategy.nameTag = "TEST_STRAT"
            self.strategy.useLimitOrders = True
            self.strategy.validateQuantity = True
            self.strategy.validateBidAskSpread = True
            self.strategy.bidAskSpreadRatio = 0.25
            self.strategy.limitOrderExpiration = timedelta(minutes=1)
            self.strategy.slippage = 0.01
            self.strategy.targetPremiumPct = None
            self.strategy.targetPremium = 1.0
            self.strategy.maxOrderQuantity = 10
            self.strategy.computeGreeks = True
            self.strategy.underlyingSymbol = "SPY"
            self.strategy.marketCloseCutoffTime = time(15, 45)
            
            # Add limit order price parameters
            self.strategy.limitOrderAbsolutePrice = None
            self.strategy.limitOrderRelativePriceAdjustment = 0.2
            self.strategy.minPremium = 0.9
            self.strategy.maxPremium = 1.2
            
            # Make sure these return actual numbers instead of MagicMocks
            type(self.strategy).minPremium = property(lambda x: 0.9)
            type(self.strategy).maxPremium = property(lambda x: 1.2)
            type(self.strategy).limitOrderAbsolutePrice = property(lambda x: None)
            type(self.strategy).limitOrderRelativePriceAdjustment = property(lambda x: 0.2)
            
            # Update parameter mock to handle different parameter types
            def mock_parameter(param_name, default=None):
                param_map = {
                    "profitTarget": 0.5,
                    "profitTargetMethod": "Premium",
                    "thetaProfitDays": 0,
                }
                return param_map.get(param_name, default)
            
            self.strategy.parameter = MagicMock(side_effect=mock_parameter)
            
            # Add required attributes for BSM initialization
            self.algorithm.riskFreeRate = 0.02
            self.algorithm.portfolioMarginStress = 0.12
            
            # Add working orders dictionary
            self.algorithm.workingOrders = {}
            self.algorithm.openPositions = {}
            self.algorithm.allPositions = {}
            
            self.algorithm.lastTradingDay = MagicMock(return_value=datetime.now().date())
            
            self.order = Order(self.algorithm, self.strategy)
            
            # Mock common attributes
            self.algorithm.logger = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Portfolio = MagicMock(
                TotalPortfolioValue=100000,
                TotalProfit=1000,
                MarginRemaining=50000
            )
            # Mock Securities with GetLastKnownPrice
            security_mock = MagicMock()
            security_mock.Price = 100
            self.algorithm.Securities = {"SPY": security_mock}
            self.algorithm.GetLastKnownPrice = MagicMock(return_value=MagicMock(Price=100))
            self.algorithm.Time = datetime.now()
            
            # Create mock contract using OptionContract from mocks
            self.mock_contract = OptionContract(
                symbol=Symbol.Create("SPY"),
                security=None
            )
            # Configure the contract properties
            self.mock_contract._strike = 100.0
            self.mock_contract._right = OptionRight.Call
            self.mock_contract._expiry = datetime.now() + timedelta(days=30)
            self.mock_contract._implied_volatility = 0.2
            self.mock_contract._greeks = MagicMock(
                delta=0.5,
                gamma=0.1,
                theta=-0.1,
                vega=0.2,
                rho=0.05
            )
            self.mock_contract._bid_price = 0.95
            self.mock_contract._ask_price = 1.05
            self.mock_contract._last_price = 1.0
            self.mock_contract._underlying_last_price = 100.0
            
            # Add property for BSM calculations
            type(self.mock_contract).BSMImpliedVolatility = property(
                lambda x: x._implied_volatility
            )
            
            # Mock BSM methods
            self.order.bsm.setGreeks = MagicMock()
            self.order.bsm.bsmPrice = MagicMock(return_value=1.0)
            self.order.bsm.isITM = MagicMock(return_value=True)

    with context('initialization'):
        with it('initializes with correct attributes'):
            expect(self.order.context).to(equal(self.algorithm))
            expect(self.order.strategy).to(equal(self.strategy))
            expect(self.order.name).to(equal("TestStrategy"))
            expect(self.order.nameTag).to(equal("TEST_STRAT"))
            expect(hasattr(self.order, 'bsm')).to(be_true)
            expect(hasattr(self.order, 'contractUtils')).to(be_true)
            expect(hasattr(self.order, 'strategyBuilder')).to(be_true)

    with context('fValue'):
        with it('calculates financial value correctly'):
            # Mock BSM price calculation
            self.order.bsm.bsmPrice = MagicMock(return_value=1.0)
            
            result = self.order.fValue(
                spotPrice=100,
                contracts=[self.mock_contract],
                sides=[1],
                openPremium=0.5
            )
            
            expect(result).to(equal(1.5))  # openPremium + bsmPrice * side

    with context('getPayoff'):
        with it('calculates call option payoff correctly'):
            result = self.order.getPayoff(
                spotPrice=110,
                contracts=[self.mock_contract],
                sides=[1]
            )
            
            expect(result).to(equal(10))  # max(0, spotPrice - strike)

        with it('calculates put option payoff correctly'):
            self.mock_contract._right = OptionRight.Put
            
            result = self.order.getPayoff(
                spotPrice=90,
                contracts=[self.mock_contract],
                sides=[1]
            )
            
            expect(result).to(equal(10))  # max(0, strike - spotPrice)

    with context('computeOrderMaxLoss'):
        with before.each:
            # Mock the underlying price to be 100
            self.order.contractUtils.getUnderlyingLastPrice = MagicMock(return_value=100)

        with it('computes max loss for call option'):
            result = self.order.computeOrderMaxLoss(
                contracts=[self.mock_contract],
                sides=[-1]  # Short call
            )
            
            # The max loss is calculated at 10x the underlying price
            # For a short call with strike 100 and underlying at 100*10=1000
            # Max loss = -(1000 - 100) = -900
            expect(result).to(equal(-900))

        with it('computes max loss for put option'):
            self.mock_contract._right = OptionRight.Put
            
            result = self.order.computeOrderMaxLoss(
                contracts=[self.mock_contract],
                sides=[-1]  # Short put
            )
            
            # For a put, max loss is the strike price
            expect(result).to(equal(-100))

        with it('returns 0 when no contracts'):
            result = self.order.computeOrderMaxLoss(
                contracts=[],
                sides=[]
            )
            expect(result).to(equal(0))

        with it('handles multiple contracts'):
            second_contract = MagicMock(
                Symbol=Symbol.Create("SPY"),
                Strike=110,
                Right=OptionRight.Put,
                Expiry=datetime.now() + timedelta(days=30)
            )
            
            result = self.order.computeOrderMaxLoss(
                contracts=[self.mock_contract, second_contract],
                sides=[-1, 1]  # Short call, long put
            )
            
            # For short call (strike 100) and long put (strike 110):
            # At spot = 0: Put payoff = 110, Call payoff = 0
            # At spot = 100: Put payoff = 10, Call payoff = 0
            # At spot = 110: Put payoff = 0, Call payoff = -10
            # At spot = 1000: Put payoff = 0, Call payoff = -900
            # Max loss = -900 (from short call at high prices)
            expect(result).to(equal(-900))

    with context('getMaxOrderQuantity'):
        with it('returns base max order quantity when no target premium percentage'):
            result = self.order.getMaxOrderQuantity()
            expect(result).to(equal(10))

        with it('scales max order quantity with portfolio profit'):
            self.strategy.targetPremiumPct = 0.01
            # Set initial account value
            self.algorithm.initialAccountValue = 100000
            # Set portfolio profit to 20% to ensure we see scaling
            self.algorithm.Portfolio.TotalProfit = 20000  # 20% profit
            
            result = self.order.getMaxOrderQuantity()
            # maxOrderQuantity * (1 + TotalProfit/initialAccountValue)
            # 10 * (1 + 20000/100000) = 10 * 1.2 = 12
            expect(result).to(equal(12))

        with it('never returns less than initial max order quantity'):
            self.strategy.targetPremiumPct = 0.01
            self.algorithm.initialAccountValue = 100000
            # Set portfolio loss
            self.algorithm.Portfolio.TotalProfit = -20000  # 20% loss
            
            result = self.order.getMaxOrderQuantity()
            # Should not go below initial maxOrderQuantity even with losses
            expect(result).to(equal(10))

    with context('getOrderDetails'):
        with before.each:
            self.order_params = {
                "contracts": [self.mock_contract],
                "sides": [1],
                "strategy": "Test Strategy",
                "sell": True
            }
            
            self.order.contractUtils.midPrice = MagicMock(return_value=1.0)
            self.order.contractUtils.bidAskSpread = MagicMock(return_value=0.05)
            self.order.contractUtils.getUnderlyingLastPrice = MagicMock(return_value=100)

        with it('returns None when no contracts'):
            result = self.order.getOrderDetails(
                contracts=[],
                sides=[],
                strategy="Test"
            )
            expect(result).to(be_none)

        with it('builds order details correctly'):
            result = self.order.getOrderDetails(**self.order_params)
            
            expect(result).to(have_key("strategyId"))
            expect(result).to(have_key("expiry"))
            expect(result).to(have_key("orderMidPrice"))
            expect(result).to(have_key("limitOrderPrice"))
            expect(result).to(have_key("orderQuantity"))
            expect(result["creditStrategy"]).to(be_true)

    with context('order type methods'):
        with before.each:
            self.order.strategyBuilder.getPuts = MagicMock(return_value=[self.mock_contract])
            self.order.strategyBuilder.getCalls = MagicMock(return_value=[self.mock_contract])
            # Mock getSpread to return a list of two contracts
            self.order.strategyBuilder.getSpread = MagicMock(
                return_value=[self.mock_contract, self.mock_contract]
            )
            self.order.strategyBuilder.getATMStrike = MagicMock(return_value=100)
            # Update getPuts for butterfly to return list
            self.order.strategyBuilder.getPuts = MagicMock(side_effect=lambda *args, **kwargs: [self.mock_contract])
            self.order.getOrderDetails = MagicMock(return_value={"test": "order"})

        with it('creates naked order correctly'):
            result = self.order.getNakedOrder(
                contracts=[self.mock_contract],
                type="call",
                strike=100
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates straddle order correctly'):
            result = self.order.getStraddleOrder(
                contracts=[self.mock_contract],
                strike=100
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates strangle order correctly'):
            result = self.order.getStrangleOrder(
                contracts=[self.mock_contract],
                callDelta=0.3,
                putDelta=0.3
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates spread order correctly'):
            result = self.order.getSpreadOrder(
                contracts=[self.mock_contract],
                type="call",
                strike=100
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates iron condor order correctly'):
            result = self.order.getIronCondorOrder(
                contracts=[self.mock_contract],
                callDelta=0.3,
                putDelta=0.3
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates iron fly order correctly'):
            result = self.order.getIronFlyOrder(
                contracts=[self.mock_contract]
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates butterfly order correctly'):
            # Create a custom list class for concatenation
            class MockList(list):
                def __add__(self, other):
                    if isinstance(other, list):
                        return MockList(super().__add__(other))
                    return MockList(super().__add__([other]))
            
            # Create mock contracts using our custom list
            put_spread = MockList([self.mock_contract, self.mock_contract])
            wing = MockList([self.mock_contract])
            
            # Mock getSpread to return our custom list for putSpread
            def mock_getspread(*args, **kwargs):
                if 'sortByStrike' in kwargs and kwargs['sortByStrike']:
                    return put_spread
                return put_spread
            
            self.order.strategyBuilder.getSpread = MagicMock(side_effect=mock_getspread)
            
            # Mock getPuts to return list for wings
            self.order.strategyBuilder.getPuts = MagicMock(return_value=wing)
            
            # Mock getCalls to also return list
            self.order.strategyBuilder.getCalls = MagicMock(return_value=wing)
            
            result = self.order.getButterflyOrder(
                contracts=[self.mock_contract],
                type="put"
            )
            expect(result).to(equal({"test": "order"}))

        with it('creates custom order correctly'):
            self.order.strategyBuilder.getContracts = MagicMock(
                return_value=[self.mock_contract]
            )
            
            result = self.order.getCustomOrder(
                contracts=[self.mock_contract],
                types=["call"],
                deltas=[0.3],
                sides=[1]
            )
            expect(result).to(equal({"test": "order"})) 