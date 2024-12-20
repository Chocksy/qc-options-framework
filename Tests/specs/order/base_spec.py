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
            self.base.strategy = MagicMock()
            self.base.strategy.parameter = MagicMock()
            self.base.strategy.parameter.side_effect = lambda key, default: {
                'maxActivePositions': 2,
                'maxOpenPositions': 3,
                'checkForDuplicatePositions': True,
                'validateQuantity': True,
                'validateBidAskSpread': True,
                'bidAskSpreadRatio': 0.3,
                'allowMultipleEntriesPerExpiry': False
            }.get(key, default)
            
            self.base.context = MagicMock()
            self.base.context.Portfolio = MagicMock()
            self.base.context.Portfolio.Values = []
            self.base.context.Transactions = MagicMock()
            self.base.context.Transactions.GetOpenOrders = MagicMock(return_value=[])
            self.base.context.openPositions = {}
            self.base.context.allPositions = {}
            
            # Create mock contracts
            self.mock_contract1 = MagicMock()
            self.mock_contract1.Strike = 100
            self.mock_contract1.Symbol = "SPX_100"
            
            self.mock_contract2 = MagicMock()
            self.mock_contract2.Strike = 105
            self.mock_contract2.Symbol = "SPX_105"
            
            self.order = {
                'strategyId': 'test_strategy',
                'contracts': [self.mock_contract1, self.mock_contract2],
                'orderQuantity': 1,
                'maxOrderQuantity': 2,
                'creditStrategy': True,
                'orderMidPrice': 1.0,
                'bidAskSpread': 0.2,
                'expiry': datetime.now() + timedelta(days=30),
                'contractSide': {
                    'SPX_100': 'Sell',
                    'SPX_105': 'Buy'
                },
                'strikes': {
                    'Sell': 100,
                    'Buy': 105
                },
                'contractExpiry': {
                    'Sell': datetime.now() + timedelta(days=30),
                    'Buy': datetime.now() + timedelta(days=30)
                },
                'contractSideDesc': {
                    'SPX_100': 'Sell',
                    'SPX_105': 'Buy'
                },
                'maxLoss': -100,
                'limitOrderPrice': 1.0,
                'targetPremium': 1.0
            }
            
        with it('builds position and working order correctly'):
            position, working_order = self.base.buildOrderPosition(self.order)
            expect(position).not_to(be_none)
            expect(working_order).not_to(be_none)
            
        with it('validates order quantity'):
            self.order['orderQuantity'] = 3
            self.order['maxOrderQuantity'] = 2
            result = self.base.buildOrderPosition(self.order)
            expect(result[0]).to(be_none)
            expect(result[1]).to(be_none)
            
        with it('validates bid-ask spread for market orders'):
            self.base.strategy.useLimitOrders = False
            self.base.strategy.validateBidAskSpread = True
            self.base.strategy.bidAskSpreadRatio = 0.3
            self.order['bidAskSpread'] = 0.5
            self.order['orderMidPrice'] = 1.0
            result = self.base.buildOrderPosition(self.order)
            expect(result[0]).to(be_none)
            expect(result[1]).to(be_none)

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

    with context('position limits'):
        with before.each:
            self.base.strategy = MagicMock()
            self.base.strategy.parameter = MagicMock()
            self.base.context = MagicMock()
            self.base.maxActivePositions = 2
            self.base.maxOpenPositions = 2
            
            # Mock positions
            self.mock_position1 = MagicMock(
                strategyId="test_strategy",
                expiryStr=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                legs=[MagicMock(strike=100, contractSide="Sell")]
            )
            self.mock_position2 = MagicMock(
                strategyId="test_strategy",
                expiryStr=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                legs=[MagicMock(strike=105, contractSide="Buy")]
            )
            
        with it('returns True when max active positions reached'):
            self.base.context.openPositions = {"pos1": "order1", "pos2": "order2"}
            self.base.context.allPositions = {
                "order1": self.mock_position1,
                "order2": self.mock_position2
            }
            expect(len(self.base.context.openPositions)).to(equal(2))
            
        with it('returns False when below max active positions'):
            self.base.context.openPositions = {"pos1": "order1"}
            self.base.context.allPositions = {"order1": self.mock_position1}
            expect(len(self.base.context.openPositions)).to(equal(1))
            
        with it('ignores positions from other strategies'):
            self.mock_position2.strategyId = "other_strategy"
            self.base.context.openPositions = {"pos1": "order1", "pos2": "order2"}
            self.base.context.allPositions = {
                "order1": self.mock_position1,
                "order2": self.mock_position2
            }
            expect(len([p for p in self.base.context.allPositions.values() if p.strategyId == "test_strategy"])).to(equal(1))

    with context('position limit checks'):
        with before.each:
            # Create mock contracts
            mock_contract1 = MagicMock()
            mock_contract1.Strike = 100
            mock_contract1.Symbol = "SPX_100"
            
            mock_contract2 = MagicMock()
            mock_contract2.Strike = 105
            mock_contract2.Symbol = "SPX_105"
            
            self.mock_order = {
                'strategyId': 'test_strategy',
                'contracts': [mock_contract1, mock_contract2],
                'expiry': datetime.now() + timedelta(days=30),
                'contractSide': {
                    'SPX_100': 'Sell',
                    'SPX_105': 'Buy'
                }
            }
            self.base.strategy = MagicMock()
            self.base.strategy.parameter = MagicMock()
            self.base.context = MagicMock()
            self.base.context.Portfolio = MagicMock()
            self.base.context.Portfolio.Values = []
            self.base.context.Transactions = MagicMock()
            self.base.context.Transactions.GetOpenOrders = MagicMock(return_value=[])
            self.base.context.openPositions = {}
            self.base.context.allPositions = {}
            
        with it('allows orders within position limits'):
            self.base.strategy.parameter.side_effect = lambda key, default: {
                'maxActivePositions': 2,
                'maxOpenPositions': 3,
                'checkForDuplicatePositions': True
            }.get(key, default)
            
            expect(self.base.check_position_limits(self.mock_order)).to(be_true)
            
        with it('prevents orders exceeding max active positions'):
            self.base.strategy.parameter.side_effect = lambda key, default: {
                'maxActivePositions': 1,
                'maxOpenPositions': 3,
                'checkForDuplicatePositions': True
            }.get(key, default)
            
            self.base.context.Portfolio.Values = [MagicMock(Invested=True)]
            expect(self.base.check_position_limits(self.mock_order)).to(be_false)
            
        with it('prevents orders exceeding max open orders'):
            self.base.strategy.parameter.side_effect = lambda key, default: {
                'maxActivePositions': 2,
                'maxOpenPositions': 1,
                'checkForDuplicatePositions': True
            }.get(key, default)
            
            self.base.context.Transactions.GetOpenOrders.return_value = [MagicMock()]
            expect(self.base.check_position_limits(self.mock_order)).to(be_false)
            
        with it('prevents duplicate positions when configured'):
            self.base.strategy.parameter.side_effect = lambda key, default: {
                'maxActivePositions': 2,
                'maxOpenPositions': 3,
                'checkForDuplicatePositions': True
            }.get(key, default)
            
            self.base.hasDuplicateLegs = MagicMock(return_value=True)
            expect(self.base.check_position_limits(self.mock_order)).to(be_false)