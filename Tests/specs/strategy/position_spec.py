from mamba import description, context, it, before, after
from expects import expect, equal, be_true, be_false, raise_error, contain
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from datetime import datetime, time

# Patch all Tools modules to avoid circular imports
with patch.dict('sys.modules', ModuleMocks.get_all()):
    with patch_imports()[0], patch_imports()[1]:
        from Strategy.Position import Position, Leg, OrderType
        from AlgorithmImports import OptionContract, Symbol, OptionRight

with description('Position') as self:
    with before.each:
        # Patch all Tools modules inside the test context
        with patch.dict('sys.modules', ModuleMocks.get_all()):
            with patch_imports()[0], patch_imports()[1]:
                # Create a position with legs
                self.position = Position(
                    orderId="123",
                    orderTag="TEST_ORDER",
                    strategy="TestStrategy",
                    strategyTag="TEST",
                    expiryStr="20240101"
                )
                
                # Create a symbol with Underlying property
                self.symbol_mock = MagicMock()
                self.symbol_mock.Underlying = "TEST"
                
                # Create and add legs to position
                self.leg = Leg(
                    key="leg1",
                    symbol=self.symbol_mock,
                    quantity=1,
                    strike=100.0,
                    contract=MagicMock(Right=OptionRight.Call)
                )
                self.position.legs.append(self.leg)

    with context('utility methods'):
        with it('returns correct underlying symbol'):
            expect(self.position.underlyingSymbol()).to(equal("TEST"))

    with context('strategy type properties'):
        with before.each:
            self.credit_strategies = [
                "PutCreditSpread", "CallCreditSpread", "IronCondor", 
                "IronFly", "CreditButterfly", "ShortStrangle", 
                "ShortStraddle", "ShortCall", "ShortPut"
            ]
            self.debit_strategies = [
                "DebitButterfly", "ReverseIronFly", "ReverseIronCondor",
                "CallDebitSpread", "PutDebitSpread", "LongStrangle",
                "LongStraddle", "LongCall", "LongPut"
            ]

        with it('correctly identifies credit strategies'):
            for strategy in self.credit_strategies:
                self.position.strategyId = strategy
                expect(self.position.isCreditStrategy).to(be_true)
                expect(self.position.isDebitStrategy).to(be_false)

        with it('correctly identifies debit strategies'):
            for strategy in self.debit_strategies:
                self.position.strategyId = strategy
                expect(self.position.isDebitStrategy).to(be_true)
                expect(self.position.isCreditStrategy).to(be_false)

    with context('leg properties'):
        with it('correctly identifies call options'):
            expect(self.leg.isCall).to(be_true)
            expect(self.leg.isPut).to(be_false)

        with it('correctly identifies put options'):
            self.leg.contract.Right = OptionRight.Put
            expect(self.leg.isPut).to(be_true)
            expect(self.leg.isCall).to(be_false)

        with it('correctly identifies bought/sold legs'):
            self.leg.contractSide = 1
            expect(self.leg.isBought).to(be_true)
            expect(self.leg.isSold).to(be_false)

            self.leg.contractSide = -1
            expect(self.leg.isSold).to(be_true)
            expect(self.leg.isBought).to(be_false)

    with context('strategy module and parameters'):
        with before.each:
            # Set up sys.modules with our mocks for each test
            self.mock_modules = ModuleMocks.get_all()
            self.mock_patch = patch.dict('sys.modules', self.mock_modules)
            self.mock_patch.start()

        with after.each:
            self.mock_patch.stop()

        with it('retrieves strategy parameters'):
            strategy_mock = MagicMock()
            strategy_mock.name = "SPXic"
            self.position.strategy = strategy_mock
            param_value = self.position.strategyParam('targetPremiumPct')
            expect(param_value).to(equal(0.01))

        with it('returns default value for unknown parameter'):
            strategy_mock = MagicMock()
            strategy_mock.name = "SPXic"
            self.position.strategy = strategy_mock
            param_value = self.position.strategyParam('unknown_param')
            expect(param_value).to(equal(0.0))

    with context('position value calculation'):
        with before.each:
            self.context = MagicMock()
            self.context.executionTimer = MagicMock()
            
            # Set up strategy mock for all position value tests
            strategy_mock = MagicMock()
            strategy_mock.name = "TestStrategy"
            self.position.strategy = strategy_mock

        with it('calculates position value correctly'):
            # For a short position:
            # - openPremium is positive (we received premium)
            # - orderMidPrice is negative (we're buying back)
            self.position.openOrder.premium = 2.0  # We received 2.0 premium when selling
            self.position.orderQuantity = 1
            self.position.contractSide = {self.symbol_mock: -1}  # Short position
            
            # Mock multiple strategy parameters
            strategy_params = {
                'slippage': 0.01,  # 1% slippage
                'validateBidAskSpread': False,  # Disable bid-ask spread validation
                'bidAskSpreadRatio': 0.25  # Not used when validation is disabled
            }
            
            def mock_strategy_param(param_name):
                return strategy_params.get(param_name, 0.0)
            
            with patch.object(Position, 'strategyParam', side_effect=mock_strategy_param):
                self.position.getPositionValue(self.context)
                
                # For a short position (contractSide = -1), orderMidPrice will be negative
                expect(self.position.orderMidPrice).to(equal(-1.0))
                expect(self.position.bidAskSpread).to(equal(0.1))
                
                # PnL calculation:
                # openPremium(2.0) + orderMidPrice(-1.0) * orderQuantity(1) = 1.0
                # We received 2.0 when selling, need to pay 1.0 to buy back, profit is 1.0
                expect(self.position.positionPnL).to(equal(1.0))

    with context('order cancellation'):
        with it('cancels orders and updates tracking'):
            context = MagicMock()
            context.logger = MagicMock()
            context.charting = MagicMock()
            context.Transactions = MagicMock()
            
            # Setup mock order ticket
            ticket = MagicMock()
            context.Transactions.GetOrderTicket.return_value = ticket
            
            # Add transaction IDs to the order
            self.position.openOrder.transactionIds = [1, 2]
            
            self.position.cancelOrder(context, 'open', 'Test cancellation')
            
            expect(self.position.orderCancelled).to(be_true)
            expect(ticket.Cancel.call_count).to(equal(2))
            context.logger.info.assert_called()
            context.charting.updateStats.assert_called_with(self.position)

    with context('expiry calculations'):
        with it('determines last trading day correctly'):
            context = MagicMock()
            expected_date = datetime(2024, 1, 1).date()
            context.lastTradingDay.return_value = expected_date
            
            result = self.position.expiryLastTradingDay(context)
            expect(result).to(equal(expected_date))

        with it('calculates market close cutoff time'):
            context = MagicMock()
            last_trading_day = datetime(2024, 1, 1).date()
            context.lastTradingDay.return_value = last_trading_day
            
            # Mock strategy parameter for market close time
            with patch.object(Position, 'strategyParam', return_value=time(16, 0)):
                result = self.position.expiryMarketCloseCutoffDttm(context)
                expected = datetime.combine(last_trading_day, time(16, 0))
                expect(result).to(equal(expected))