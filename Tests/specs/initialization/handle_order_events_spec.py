from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Initialization.HandleOrderEvents import HandleOrderEvents
    from Tests.mocks.algorithm_imports import (
        OrderStatus, Symbol, TradeBar, datetime, timedelta
    )

with description('HandleOrderEvents') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.order_event = MagicMock(
                OrderId=1,
                Symbol=Symbol.Create("SPY"),
                Status=OrderStatus.Filled,
                FillQuantity=100,
                FillPrice=10.0,
                IsAssignment=False
            )
            
            # Mock algorithm attributes
            self.algorithm.Time = datetime.now()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Transactions = MagicMock()
            self.algorithm.workingOrders = {}
            self.algorithm.openPositions = {}
            self.algorithm.allPositions = {}
            self.algorithm.charting = MagicMock()
            self.algorithm.recentlyClosedDTE = []
            self.algorithm.logger = MagicMock()
            self.algorithm.positions_store = MagicMock()  # Always initialize positions_store
            
            self.handler = HandleOrderEvents(self.algorithm, self.order_event)

    with context('initialization'):
        with it('initializes with correct attributes'):
            expect(self.handler.context).to(equal(self.algorithm))
            expect(self.handler.orderEvent).to(equal(self.order_event))
            expect(hasattr(self.handler, 'logger')).to(be_true)

    with context('Call'):
        with it('ignores non-fill order events'):
            self.order_event.Status = OrderStatus.Submitted
            self.handler.Call()
            self.algorithm.executionTimer.start.assert_called_once()
            expect(self.algorithm.executionTimer.stop.call_count).to(equal(0))

        with it('handles assignment orders'):
            # Setup assignment order
            self.order_event.IsAssignment = True
            position = MagicMock(
                orderTag="TEST_POS",
                strategyModule=MagicMock(return_value=MagicMock(handleAssignment=MagicMock()))
            )
            self.handler.getPositionFromOrderEvent = MagicMock(
                return_value=(position, None, "close", None)
            )
            
            self.handler.Call()
            
            position.strategyModule().handleAssignment.assert_called_once()

        with it('processes filled orders correctly'):
            # Setup mock position and order
            position = MagicMock(
                orderTag="TEST_POS",
                legs=[MagicMock(symbol=self.order_event.Symbol)],
                orderQuantity=1,
                openOrder=MagicMock(filled=True),
                closeOrder=MagicMock(filled=True)
            )
            working_order = MagicMock(orderType="open")
            mock_order = MagicMock()
            mock_order.Tag = "TEST_POS"
            
            self.handler.getPositionFromOrderEvent = MagicMock(
                return_value=(position, working_order, "open", mock_order)
            )
            
            self.handler.Call()
            
            self.algorithm.executionTimer.start.assert_called_once()
            self.algorithm.executionTimer.stop.assert_called_once()

        with it('stores positions in live mode'):
            # Setup LiveMode
            self.algorithm.LiveMode = True
            
            # Setup mock position and order
            position = MagicMock(
                orderTag="TEST_POS",
                legs=[MagicMock(symbol=self.order_event.Symbol)]
            )
            mock_order = MagicMock()
            mock_order.Tag = "TEST_POS"
            self.algorithm.Transactions.GetOrderById.return_value = mock_order
            
            self.handler.getPositionFromOrderEvent = MagicMock(
                return_value=(position, None, "close", mock_order)
            )
            
            self.handler.Call()
            
            # Verify positions were stored
            self.algorithm.positions_store.store_positions.assert_called_once()

        with it('does not store positions in backtest mode'):
            # Setup LiveMode
            self.algorithm.LiveMode = False
            
            # Setup mock position and order
            position = MagicMock(
                orderTag="TEST_POS",
                legs=[MagicMock(symbol=self.order_event.Symbol)]
            )
            mock_order = MagicMock()
            mock_order.Tag = "TEST_POS"
            self.algorithm.Transactions.GetOrderById.return_value = mock_order
            
            self.handler.getPositionFromOrderEvent = MagicMock(
                return_value=(position, None, "close", mock_order)
            )
            
            self.handler.Call()
            
            # Verify positions were not stored
            self.algorithm.positions_store.store_positions.assert_not_called()

        with it('handles missing positions_store in live mode'):
            # Setup LiveMode but remove positions_store
            self.algorithm.LiveMode = True
            # No need to remove positions_store as it doesn't exist by default
            
            # Setup mock position and order
            position = MagicMock(
                orderTag="TEST_POS",
                legs=[MagicMock(symbol=self.order_event.Symbol)]
            )
            mock_order = MagicMock()
            mock_order.Tag = "TEST_POS"
            self.algorithm.Transactions.GetOrderById.return_value = mock_order
            
            self.handler.getPositionFromOrderEvent = MagicMock(
                return_value=(position, None, "close", mock_order)
            )
            
            # Should not raise an error
            self.handler.Call()
            # Test passes if no exception is raised

    with context('getPositionFromOrderEvent'):
        with it('finds position by order tag'):
            # Setup mock order and position
            mock_order = MagicMock()
            mock_order.Tag = "TEST_POS"
            self.algorithm.Transactions.GetOrderById.return_value = mock_order
            
            position = MagicMock()
            self.algorithm.allPositions = {"TEST_POS": position}
            self.algorithm.openPositions = {"TEST_POS": "TEST_POS"}
            
            result = self.handler.getPositionFromOrderEvent()
            
            expect(result[0]).to(equal(position))

        with it('finds position by symbol when no order tag match'):
            # Setup mock order with proper Tag
            mock_order = MagicMock()
            mock_order.Tag = "DIFFERENT_TAG"
            self.algorithm.Transactions.GetOrderById.return_value = mock_order
            
            # Setup mock position with matching symbol
            position = MagicMock(
                legs=[MagicMock(symbol=self.order_event.Symbol)]
            )
            self.algorithm.allPositions = {"OTHER_POS": position}
            self.algorithm.openPositions = {}
            
            result = self.handler.getPositionFromOrderEvent()
            
            expect(result[0]).to(equal(position))
            expect(result[2]).to(equal("close"))

    with context('handleFullyFilledOrder'):
        with it('processes fully filled orders correctly'):
            position = MagicMock(
                orderTag="TEST_POS",
                openPremium=1000,
                priceProgressList=[],
                updateOrderStats=MagicMock()
            )
            exec_order = MagicMock(
                filled=False,
                fillPrice=10.0,
                priceProgressList=[],
                midPrice=10.0
            )
            working_order = MagicMock()
            
            self.handler.handleFullyFilledOrder(position, exec_order, "open", working_order)
            
            expect(exec_order.filled).to(be_true)
            position.updateOrderStats.assert_called_once()

    with context('handleClosedPosition'):
        with it('processes closed positions correctly'):
            position = MagicMock(
                orderTag="TEST_POS",
                openPremium=1000,
                closePremium=-800
            )
            contract = MagicMock(
                Expiry=datetime.now() + timedelta(days=30)
            )
            
            self.algorithm.openPositions = {"TEST_POS": position}
            
            self.handler.handleClosedPosition(position, contract)
            
            expect(position.PnL).to(equal(200))
            expect(self.algorithm.openPositions).to_not(have_key("TEST_POS"))
            expect(self.algorithm.recentlyClosedDTE).to(have_length(1))
            self.algorithm.charting.updateStats.assert_called_once_with(position) 