from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Order.Base import Base
    from Tests.mocks.algorithm_imports import (
        OrderStatus, Symbol, TradeBar, datetime, timedelta,
        Insight, InsightDirection, PortfolioTarget
    )

with description('Base') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Fix the strategy mock setup
            self.strategy = MagicMock()
            self.strategy.name = "TestStrategy"  # Set as string instead of MagicMock
            self.strategy.nameTag = "TEST_STRAT" # Set as string instead of MagicMock
            
            self.base = Base(self.algorithm, self.strategy)
            
            # Mock common attributes
            self.algorithm.logger = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = {}
            self.algorithm.openPositions = {}
            self.algorithm.workingOrders = {}
            self.algorithm.Time = datetime.now()

    with context('initialization'):
        with it('initializes with correct attributes'):
            expect(self.base.context).to(equal(self.algorithm))
            expect(self.base.strategy).to(equal(self.strategy))
            expect(self.base.name).to(equal("TestStrategy"))
            expect(self.base.nameTag).to(equal("TEST_STRAT"))
            expect(hasattr(self.base, 'logger')).to(be_true)
            expect(hasattr(self.base, 'contractUtils')).to(be_true)

    with context('updateChain'):
        with it('updates context chain'):
            mock_chain = MagicMock()
            self.base.updateChain(mock_chain)
            expect(self.algorithm.chain).to(equal(mock_chain))

    with context('buildOrderPosition'):
        with before.each:
            self.mock_contract = MagicMock(
                Symbol=Symbol.Create("SPY"),
                Strike=100,
                Right="Call",
                Expiry=datetime.now() + timedelta(days=30)
            )
            self.order = {
                "contracts": [self.mock_contract],
                "strategyId": "TEST_STRAT",
                "contractSide": {self.mock_contract.Symbol: 1},
                "contractSideDesc": {self.mock_contract.Symbol: "longCall"},
                "strikes": {"longCall": 100},
                "expiry": datetime.now() + timedelta(days=30),
                "targetPremium": 1.0,
                "maxOrderQuantity": 1,
                "orderQuantity": 1,
                "bidAskSpread": 0.05,
                "orderMidPrice": 1.0,
                "limitOrderPrice": 1.0,
                "maxLoss": -100,
                "creditStrategy": True,
                "contractExpiry": {"longCall": datetime.now() + timedelta(days=30)}
            }
            
            self.strategy.useLimitOrders = True
            self.strategy.validateQuantity = True
            self.strategy.validateBidAskSpread = True
            self.strategy.bidAskSpreadRatio = 0.25
            self.strategy.limitOrderExpiration = timedelta(minutes=1)

        with it('returns None when no contracts'):
            self.order["contracts"] = []
            result = self.base.buildOrderPosition(self.order)
            expect(result).to(equal([None, None]))

        with it('builds position and working order correctly'):
            position, working_order = self.base.buildOrderPosition(self.order)
            
            expect(position).not_to(be_none)
            expect(working_order).not_to(be_none)
            expect(position.orderTag).to(contain("TEST_STRAT"))
            expect(position.strategy).to(equal(self.base))
            expect(position.legs).to(have_length(1))
            expect(working_order.insights).to(have_length(1))

        with it('validates order quantity'):
            self.order["orderQuantity"] = 0
            result = self.base.buildOrderPosition(self.order)
            expect(result).to(equal([None, None]))

        with it('validates bid-ask spread for market orders'):
            self.strategy.useLimitOrders = False
            self.order["bidAskSpread"] = 1.0  # Make spread too wide
            result = self.base.buildOrderPosition(self.order)
            expect(result).to(equal([None, None]))

    with context('getNextOrderId'):
        with it('increments order count correctly'):
            Base.orderCount = 0
            first_id = Base.getNextOrderId()
            second_id = Base.getNextOrderId()
            
            expect(first_id).to(equal(1))
            expect(second_id).to(equal(2))

        with it('handles existing positions'):
            # Set a higher order count
            Base.orderCount = 5
            
            next_id = Base.getNextOrderId()
            # Should increment from the current orderCount
            expect(next_id).to(equal(6))

        with it('handles empty positions'):
            Base.orderCount = 0
            
            next_id = Base.getNextOrderId()
            expect(next_id).to(equal(1))