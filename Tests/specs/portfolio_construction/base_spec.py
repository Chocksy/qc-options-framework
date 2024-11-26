from mamba import description, context, it, before, after
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none, raise_error
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

# Import test helpers
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from PortfolioConstruction.Base import Base
    from Tests.mocks.algorithm_imports import (
        SecurityType, Resolution, Symbol,
        PortfolioTarget, Insight, QCAlgorithm,
        List, SecurityChanges, PortfolioConstructionModel,
        InsightDirection
    )

with description('PortfolioConstruction.Base') as self:
    with before.each:
        # Setup common test environment
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Mock common attributes
            self.algorithm.logger = MagicMock(debug=MagicMock())
            self.algorithm.debug = MagicMock()
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = MagicMock()
            self.algorithm.Time = datetime.now()
            self.algorithm.openPositions = {}
            self.algorithm.allPositions = {}
            self.algorithm.workingOrders = {}
            
            # Create Base instance
            self.base = Base(self.algorithm)

    with context('initialization'):
        with it('initializes with context'):
            expect(self.base.context).to(equal(self.algorithm))
            self.algorithm.logger.debug.assert_called_with('Base -> __init__')

    with context('CreateTargets'):
        with before.each:
            self.symbol = Symbol("SPY", SecurityType.Equity, "USA")
            self.insight = Insight(
                Symbol=self.symbol,
                Direction=InsightDirection.Up,
                Period=timedelta(days=1),
                Id="test_insight_id"
            )
            
            # Mock working order
            self.mock_order = MagicMock()
            self.mock_order.orderId = "test_order"
            self.mock_order.insights = [self.insight]
            self.mock_order.targets = []
            
            # Mock position
            self.mock_position = MagicMock()
            self.mock_position.orderQuantity = 100
            
            # Setup the algorithm state
            self.algorithm.workingOrders = {"test_order": self.mock_order}
            self.algorithm.allPositions = {"test_order": self.mock_position}

        with it('creates portfolio targets from insights'):
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            
            expect(targets).to(have_length(1))
            expect(targets[0].Symbol).to(equal(self.symbol))
            expect(targets[0].Quantity).to(equal(100))  # Direction * orderQuantity
            
            # Verify target was added to order
            expect(self.mock_order.targets).to(have_length(1))
            expect(self.mock_order.targets[0].Symbol).to(equal(self.symbol))
            expect(self.mock_order.targets[0].Quantity).to(equal(100))

        with it('handles empty insights list'):
            targets = self.base.CreateTargets(self.algorithm, [])
            expect(targets).to(have_length(0))

        with it('handles insight with no matching order'):
            # Create a new insight with a different ID
            different_symbol = Symbol("AAPL", SecurityType.Equity, "USA")
            different_insight = Insight(
                Symbol=different_symbol,
                Direction=InsightDirection.Up,
                Period=timedelta(days=1),
                Id="different_insight_id"  # Different ID
            )
            
            targets = self.base.CreateTargets(self.algorithm, [different_insight])
            expect(targets).to(have_length(0))

        with it('handles multiple insights'):
            # Create a second insight and order
            symbol2 = Symbol("AAPL", SecurityType.Equity, "USA")
            insight2 = Insight(
                Symbol=symbol2,
                Direction=InsightDirection.Down,
                Period=timedelta(days=1),
                Id="test_insight_id2"
            )
            
            # Mock second working order
            mock_order2 = MagicMock()
            mock_order2.orderId = "test_order2"
            mock_order2.insights = [insight2]
            mock_order2.targets = []
            
            # Mock second position
            mock_position2 = MagicMock()
            mock_position2.orderQuantity = 50
            
            # Add to algorithm state
            self.algorithm.workingOrders["test_order2"] = mock_order2
            self.algorithm.allPositions["test_order2"] = mock_position2
            
            targets = self.base.CreateTargets(self.algorithm, [self.insight, insight2])
            
            expect(targets).to(have_length(2))
            # First target
            expect(targets[0].Symbol).to(equal(self.symbol))
            expect(targets[0].Quantity).to(equal(100))
            # Second target
            expect(targets[1].Symbol).to(equal(symbol2))
            expect(targets[1].Quantity).to(equal(-50))  # Down direction (-1) * 50

        with it('handles insight with zero quantity'):
            self.mock_position.orderQuantity = 0
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(1))
            expect(targets[0].Quantity).to(equal(0))

        with it('handles insight with negative direction'):
            self.insight.Direction = InsightDirection.Down
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(1))
            expect(targets[0].Quantity).to(equal(-100))  # -1 * 100

        with it('handles insight with flat direction'):
            self.insight.Direction = InsightDirection.Flat
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(1))
            expect(targets[0].Quantity).to(equal(0))  # 0 * 100

        with it('handles insight with None direction'):
            self.insight.Direction = None
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(1))
            expect(targets[0].Quantity).to(equal(0))  # None * 100 should default to 0

        with it('handles insight with missing position'):
            # Remove the position from allPositions
            self.algorithm.allPositions = {}
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(0))

        with it('handles insight with None symbol'):
            self.insight.Symbol = None
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(0))

        with it('handles insight with None ID'):
            self.insight.Id = None
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(0))

        with it('handles order with empty insights list'):
            self.mock_order.insights = []
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(0))

        with it('handles order with None insights'):
            self.mock_order.insights = None
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(0))

        with it('handles position with None orderQuantity'):
            self.mock_position.orderQuantity = None
            targets = self.base.CreateTargets(self.algorithm, [self.insight])
            expect(targets).to(have_length(1))
            expect(targets[0].Quantity).to(equal(0))  # Direction * None should default to 0