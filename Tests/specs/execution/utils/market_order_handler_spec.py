from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from datetime import datetime, timedelta

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Execution.Utils.MarketOrderHandler import MarketOrderHandler
    from Tests.mocks.algorithm_imports import (
        SecurityType, Resolution, OptionRight, Symbol,
        TradeBar, PortfolioTarget, datetime, timedelta,
        OptionContract, Leg
    )

with description('Execution.Utils.MarketOrderHandler') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Mock common attributes
            self.algorithm.logger = MagicMock()
            self.algorithm.executionTimer = MagicMock(
                start=MagicMock(),
                stop=MagicMock()
            )
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = {}
            self.algorithm.logLevel = 0
            
            # Create base mock
            self.base = MagicMock()
            
            # Create handler instance
            self.handler = MarketOrderHandler(self.algorithm, self.base)
            
            # Create mock position with proper order setup
            self.position = MagicMock()
            self.position.orderTag = "TEST_ORDER"
            self.position.orderQuantity = 1
            self.position.underlyingSymbol = MagicMock(return_value="SPX")
            self.position.strategyParam = MagicMock(return_value=False)  # validateBidAskSpread = False
            
            # Create mock order with proper attributes
            mock_order = MagicMock()
            mock_order.transactionIds = []
            mock_order.priceProgressList = []
            
            # Set up position to return mock order for both open and close orders
            self.position.__getitem__ = MagicMock(return_value=mock_order)
            
            # Create mock contracts and legs
            self.contract1 = OptionContract()
            self.contract2 = OptionContract()
            
            self.leg1 = MagicMock(
                contract=self.contract1,
                contractSide=1,
                quantity=1,
                symbol="SPX_1"
            )
            self.leg2 = MagicMock(
                contract=self.contract2,
                contractSide=-1,
                quantity=1,
                symbol="SPX_2"
            )
            
            self.position.legs = [self.leg1, self.leg2]
            
            # Create mock order
            self.order = MagicMock(
                orderType="open",
                targets=[
                    MagicMock(Symbol="SPX_1"),
                    MagicMock(Symbol="SPX_2")
                ]
            )
            
            # Mock securities including the underlying
            mock_underlying = MagicMock()
            mock_underlying.Price = 100.0
            self.algorithm.Securities["SPX"] = mock_underlying
            self.algorithm.Securities["SPX_1"] = MagicMock()
            self.algorithm.Securities["SPX_2"] = MagicMock()
            
            # Mock contract utils methods
            self.handler.contractUtils.bidAskSpread = MagicMock(return_value=0.1)
            self.handler.contractUtils.midPrice = MagicMock(return_value=1.0)

    with context('initialization'):
        with it('initializes with correct attributes'):
            expect(self.handler.context).to(equal(self.algorithm))
            expect(self.handler.base).to(equal(self.base))
            expect(hasattr(self.handler, 'contractUtils')).to(be_true)
            expect(hasattr(self.handler, 'logger')).to(be_true)

    with context('call'):
        with before.each:
            # Ensure ComboMarketOrder is mocked for all tests
            self.algorithm.ComboMarketOrder = MagicMock(
                return_value=[MagicMock(OrderId="123")]
            )

        with it('handles single leg market orders'):
            # Setup single leg position
            self.position.legs = [self.leg1]
            
            # Mock MarketOrder method
            self.algorithm.MarketOrder = MagicMock()
            
            # Mock order stats methods
            self.position.updateOrderStats = MagicMock()
            self.position.updateStats = MagicMock()
            
            # Create mock order with empty transactionIds
            mock_order = MagicMock()
            mock_order.transactionIds = []
            mock_order.priceProgressList = []
            self.position.__getitem__.return_value = mock_order
            
            # Call the handler
            self.handler.call(self.position, self.order)
            
            # Verify MarketOrder was called correctly
            self.algorithm.MarketOrder.assert_called_once_with(
                "SPX_1",
                1,  # orderSide * quantity
                asynchronous=True,
                tag="TEST_ORDER"
            )

        with it('handles combo market orders'):
            # Create mock openOrder with empty transactionIds
            mock_order = MagicMock()
            mock_order.transactionIds = []
            mock_order.priceProgressList = []
            self.position.__getitem__.return_value = mock_order
            
            # Call the handler
            self.handler.call(self.position, self.order)
            
            # Verify ComboMarketOrder was called correctly
            self.algorithm.ComboMarketOrder.assert_called_once()
            
            # Get the call arguments as kwargs to safely check them
            call_args, call_kwargs = self.algorithm.ComboMarketOrder.call_args
            
            # Check the arguments
            expect(len(call_args[0])).to(equal(2))  # Two legs
            expect(call_args[1]).to(equal(1))  # orderQuantity
            expect(call_kwargs['asynchronous']).to(be_true)
            expect(call_kwargs['tag']).to(equal("TEST_ORDER"))

        with it('skips order if transaction IDs exist'):
            # Create mock openOrder with existing transactionIds
            mock_open_order = MagicMock()
            mock_open_order.transactionIds = ["123"]
            mock_open_order.priceProgressList = []
            self.position.__getitem__.return_value = mock_open_order
            
            # Call the handler
            self.handler.call(self.position, self.order)
            
            # Verify ComboMarketOrder was not called
            self.algorithm.ComboMarketOrder.assert_not_called()

        with it('respects bid-ask spread validation'):
            # Enable bid-ask spread validation
            self.position.strategyParam = MagicMock(
                side_effect=lambda x: True if x == "validateBidAskSpread" else 0.1
            )
            
            # Set wide spread
            self.handler.contractUtils.bidAskSpread = MagicMock(return_value=1.0)
            
            # Create mock openOrder
            mock_open_order = MagicMock()
            mock_open_order.transactionIds = []
            mock_open_order.priceProgressList = []
            self.position.__getitem__.return_value = mock_open_order
            
            # Call the handler
            self.handler.call(self.position, self.order)
            
            # Verify ComboMarketOrder was not called due to wide spread
            self.algorithm.ComboMarketOrder.assert_not_called()

        with it('updates order stats and position stats'):
            # Create mock openOrder with empty transactionIds
            mock_order = MagicMock()
            mock_order.transactionIds = []
            mock_order.priceProgressList = []
            self.position.__getitem__.return_value = mock_order
            
            # Mock order stats methods
            self.position.updateOrderStats = MagicMock()
            self.position.updateStats = MagicMock()
            
            # Call the handler
            self.handler.call(self.position, self.order)
            
            # Verify stats were updated
            self.position.updateOrderStats.assert_called_once_with(
                self.algorithm,
                "open"
            )
            self.position.updateStats.assert_called_once_with(
                self.algorithm,
                "open"
            )

        with it('handles timer correctly'):
            # Create mock openOrder with empty transactionIds
            mock_order = MagicMock()
            mock_order.transactionIds = []
            mock_order.priceProgressList = []
            self.position.__getitem__.return_value = mock_order
            
            # Call the handler
            self.handler.call(self.position, self.order)
            
            # Verify timer methods were called
            self.algorithm.executionTimer.start.assert_called_once()
            self.algorithm.executionTimer.stop.assert_called_once() 