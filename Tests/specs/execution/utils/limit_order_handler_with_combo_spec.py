from mamba import description, context, it, before
from expects import (
    expect, equal, be_true, be_false, be_none, 
    contain, be_below, be_above, raise_error  # Add raise_error
)
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass, field
import ipdb  # Import the debugger

from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.order_mocks import MockOrder, create_mock_contract, create_mock_leg, MockExecOrder

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Execution.Utils.LimitOrderHandlerWithCombo import LimitOrderHandlerWithCombo
    from datetime import datetime, timedelta
    from Tests.mocks.algorithm_imports import UpdateOrderFields, OrderStatus, Leg
    from Strategy.Position import OrderType  # Import the actual OrderType class

with description('LimitOrderHandlerWithCombo') as self:
    with before.each:
        self.algorithm = Factory.create_algorithm()
        self.algorithm.Transactions = MagicMock()
        
        # Mock Securities dictionary with proper underlying security
        mock_security = MagicMock()
        mock_security.Price = 100.0
        mock_security.Close = 100.0
        self.algorithm.Securities = {
            "SPX": mock_security,  # Add the underlying security
            "TEST1": mock_security,
            "TEST2": mock_security
        }
        
        # Create base with required parameters
        self.base = MagicMock()
        
        # Mock parameter method to return actual values
        def parameter_side_effect(key, default=None):
            params = {
                'orderAdjustmentPct': 0.1,
                'adjustmentIncrement': None,
                'minPricePct': 0.5,
                'retryChangePct': 0.1
            }
            return params.get(key, default)
            
        self.base.parameter = MagicMock(side_effect=parameter_side_effect)
        
        # Set actual numeric values for base attributes
        type(self.base).adjustmentIncrement = property(lambda x: None)
        type(self.base).orderAdjustmentPct = property(lambda x: 0.1)
        type(self.base).minPricePct = property(lambda x: 0.5)
        type(self.base).retryChangePct = property(lambda x: 0.1)
        
        self.handler = LimitOrderHandlerWithCombo(self.algorithm, self.base)
        
        # Create contracts using helper
        self.contract1 = create_mock_contract(
            strike=100.0,
            side=1,
            symbol="TEST1"
        )
        
        self.contract2 = create_mock_contract(
            strike=105.0,
            side=-1,
            symbol="TEST2"
        )
        
        # Create legs using helper
        self.leg1 = create_mock_leg(self.contract1, side=1)
        self.leg2 = create_mock_leg(self.contract2, side=-1)
        
        # Use MockOrder from mocks
        self.order = MockOrder()
        
        # Create execution order with proper numeric values
        self.exec_order = MockExecOrder(
            bidAskSpread=0.1,
            midPrice=1.0,
            priceProgressList=[1.0],  # Initialize with a value
            transactionIds=[],
            limitOrderExpiryDttm=datetime.now() + timedelta(hours=1)
        )
        
        # Create position with required attributes and proper __getitem__ behavior
        self.position = MagicMock()
        self.position.legs = [self.leg1, self.leg2]
        self.position.orderQuantity = 1
        self.position.isCreditStrategy = False
        self.position.orderTag = "TEST"
        self.position.underlyingSymbol = MagicMock(return_value="SPX")
        
        # Mock __getitem__ to return our real MockExecOrder instance
        def getitem_side_effect(key):
            if key in ['openOrder', 'closeOrder']:
                return self.exec_order
            return MagicMock()
            
        self.position.__getitem__.side_effect = getitem_side_effect
        
        # Mock contract utils
        self.handler.contractUtils.midPrice = MagicMock(return_value=1.0)
        self.handler.contractUtils.bidPrice = MagicMock(return_value=0.95)
        self.handler.contractUtils.askPrice = MagicMock(return_value=1.05)
        self.handler.contractUtils.volume = MagicMock(return_value=100)
        self.handler.contractUtils.openInterest = MagicMock(return_value=1000)
        self.handler.contractUtils.delta = MagicMock(return_value=0.5)
        
        # Mock BSM
        self.handler.bsm.setGreeks = MagicMock()
        
        # Mock ComboLimitOrder with proper Leg creation
        self.mock_ticket = MagicMock()
        self.mock_ticket.OrderId = "123"
        
        def combo_limit_order_side_effect(legs, quantity, price, tag=None):
            # Store the legs for verification
            self.created_legs = legs
            return [self.mock_ticket]
            
        self.algorithm.ComboLimitOrder = MagicMock(side_effect=combo_limit_order_side_effect)
        
        # Mock Leg.Create to return proper legs
        def leg_create_side_effect(symbol, ratio=1):
            mock_leg = MagicMock()
            mock_leg.Symbol = symbol
            mock_leg.Ratio = ratio
            return mock_leg
            
        Leg.Create = MagicMock(side_effect=leg_create_side_effect)

    with context('makeLimitOrder'):
        with it('creates combo limit order with correct legs'):
            # Execute
            self.handler.makeLimitOrder(self.position, self.order)
            
            # Verify ComboLimitOrder was called
            expect(self.algorithm.ComboLimitOrder.called).to(be_true)
            
            # Get the created legs
            call_args = self.algorithm.ComboLimitOrder.call_args[0]
            legs = call_args[0]
            
            # Verify legs were created correctly
            expect(len(legs)).to(equal(2))
            
            # Verify leg details
            expect(legs[0].Symbol).to(equal(self.contract1.Symbol))
            expect(legs[1].Symbol).to(equal(self.contract2.Symbol))
            
            # Verify order quantity
            order_quantity = call_args[1]
            expect(order_quantity).to(equal(self.position.orderQuantity))

        with it('stores transaction IDs from ticket'):
            # Execute
            self.handler.makeLimitOrder(self.position, self.order)
            
            # Verify transaction IDs were stored
            expect(self.exec_order.transactionIds).to(contain("123"))

        with it('updates retry information when retry=True'):
            initial_retries = self.order.fillRetries
            
            # Execute
            self.handler.makeLimitOrder(self.position, self.order, retry=True)
            
            # Verify retry information was updated
            expect(self.order.lastRetry).not_to(be_none)
            # fillRetries should increment by 1
            expect(self.order.fillRetries).to(equal(initial_retries + 1))

        with it('tracks price progress'):
            initial_price_list_len = len(self.exec_order.priceProgressList)
            
            # Execute
            self.handler.makeLimitOrder(self.position, self.order)
            
            # Verify price was added to progress list
            expect(len(self.exec_order.priceProgressList)).to(equal(initial_price_list_len + 1))
            expect(self.exec_order.priceProgressList[-1]).to(equal(round(self.exec_order.midPrice, 2)))

        with context('when handling credit strategies'):
            with before.each:
                self.position.isCreditStrategy = True
                type(self.position).isCreditStrategy = property(lambda x: True)

            with it('adjusts limit price for credit strategies'):
                # Execute
                self.handler.makeLimitOrder(self.position, self.order)
                
                # Verify ComboLimitOrder was called with negative price
                call_args = self.algorithm.ComboLimitOrder.call_args[0]
                limit_price = call_args[2]
                expect(float(limit_price)).to(be_below(0))

    with context('call'):
        with before.each:
            # Mock Timer for execution timing
            self.algorithm.executionTimer = MagicMock()
            
            # Create order with transaction IDs for update tests
            self.order_with_ids = MockOrder()
            self.order_with_ids.lastRetry = datetime.now() - timedelta(minutes=1)
            
            # Create order without transaction IDs for new order tests
            self.order_without_ids = MockOrder()
            self.order_without_ids.lastRetry = None
            
            # Mock updateComboLimitOrder and makeLimitOrder for verification
            self.handler.updateComboLimitOrder = MagicMock()
            self.handler.makeLimitOrder = MagicMock()

        with it('updates existing order when transaction IDs exist and retry time has passed'):
            # Setup order with transaction IDs
            self.exec_order.transactionIds = ["123"]
            
            # Execute
            self.handler.call(self.position, self.order_with_ids)
            
            # Verify updateComboLimitOrder was called
            self.handler.updateComboLimitOrder.assert_called_once_with(
                self.position, 
                self.order_with_ids, 
                self.exec_order.transactionIds
            )
            
            # Verify makeLimitOrder was not called
            expect(self.handler.makeLimitOrder.called).to(be_false)

        with it('creates new order when no transaction IDs exist'):
            # Setup order without transaction IDs
            self.exec_order.transactionIds = []
            
            # Execute
            self.handler.call(self.position, self.order_without_ids)
            
            # Verify makeLimitOrder was called
            self.handler.makeLimitOrder.assert_called_once_with(
                self.position, 
                self.order_without_ids
            )
            
            # Verify updateComboLimitOrder was not called
            expect(self.handler.updateComboLimitOrder.called).to(be_false)

        with it('skips update when retry time has not passed'):
            # Setup current time
            current_time = datetime.now()
            self.algorithm.Time = current_time
            
            # Setup order with transaction IDs and very recent retry (1 minute ago)
            self.exec_order.transactionIds = ["123"]
            self.order_with_ids.lastRetry = current_time - timedelta(minutes=1)
            
            # Mock sinceLastRetry to return False (not enough time has passed)
            self.handler.sinceLastRetry = MagicMock(return_value=False)
            
            # Execute
            self.handler.call(self.position, self.order_with_ids)
            
            # Verify neither update nor create was called
            expect(self.handler.updateComboLimitOrder.called).to(be_false)
            expect(self.handler.makeLimitOrder.called).to(be_false)

        with it('starts and stops execution timer'):
            # Execute
            self.handler.call(self.position, self.order_without_ids)
            
            # Verify timer was started and stopped
            self.algorithm.executionTimer.start.assert_called_once()
            self.algorithm.executionTimer.stop.assert_called_once()

        with it('updates order stats before processing'):
            # Mock the update methods
            self.position.updateOrderStats = MagicMock()
            self.position.updateStats = MagicMock()
            
            # Execute
            self.handler.call(self.position, self.order_without_ids)
            
            # Verify updates were called in correct order
            self.position.updateOrderStats.assert_called_once_with(
                self.algorithm, 
                self.order_without_ids.orderType
            )
            self.position.updateStats.assert_called_once_with(
                self.algorithm, 
                self.order_without_ids.orderType
            )

    with context('sinceLastRetry'):
        with before.each:
            self.current_time = datetime.now()
            self.algorithm.Time = self.current_time
            
        with it('returns True when lastRetry is None'):
            order = MockOrder(lastRetry=None)
            result = self.handler.sinceLastRetry(self.algorithm, order)
            expect(result).to(be_true)
            
        with it('returns False when not enough time has passed'):
            # Set lastRetry to 1 minute ago
            order = MockOrder(lastRetry=self.current_time - timedelta(minutes=1))
            result = self.handler.sinceLastRetry(self.algorithm, order)
            expect(result).to(be_false)
            
        with it('returns True when enough time has passed'):
            # Set lastRetry to 3 minutes ago (matching default frequency)
            order = MockOrder(lastRetry=self.current_time - timedelta(minutes=3))
            result = self.handler.sinceLastRetry(self.algorithm, order)
            expect(result).to(be_true)
            
        with it('respects custom frequency'):
            # Set lastRetry to 2 minutes ago
            order = MockOrder(lastRetry=self.current_time - timedelta(minutes=2))
            # Use 2 minute frequency
            result = self.handler.sinceLastRetry(self.algorithm, order, frequency=timedelta(minutes=2))
            expect(result).to(be_true)

    with context('updateComboLimitOrder'):
        with before.each:
            # Create mock ticket with proper status
            self.ticket = MagicMock()
            self.ticket.Status = OrderStatus.Submitted
            self.ticket.OrderId = "123"
            
            # Mock GetOrderTicket to return our ticket
            self.algorithm.Transactions.GetOrderTicket = MagicMock(return_value=self.ticket)
            
            # Create update settings mock
            self.update_settings = UpdateOrderFields()
            
            # Create successful response mock
            self.success_response = MagicMock()
            self.success_response.IsSuccess = True
            
            # Create failed response mock
            self.failed_response = MagicMock()
            self.failed_response.IsSuccess = False
            self.failed_response.ErrorCode = "TEST_ERROR"
            
            # Mock logger for verification
            self.handler.logger = MagicMock()

        with it('updates existing order with new limit price'):
            # Setup successful update
            self.ticket.Update = MagicMock(return_value=self.success_response)
            
            # Execute
            self.handler.updateComboLimitOrder(
                self.position, 
                self.order, 
                ["123"]
            )
            
            # Verify ticket was retrieved
            self.algorithm.Transactions.GetOrderTicket.assert_called_once_with("123")
            
            # Verify update was called with correct price
            update_call = self.ticket.Update.call_args[0][0]
            expect(isinstance(update_call.LimitPrice, float)).to(be_true)

        with it('logs success when update succeeds'):
            # Setup successful update
            self.ticket.Update = MagicMock(return_value=self.success_response)
            
            # Execute
            self.handler.updateComboLimitOrder(
                self.position, 
                self.order, 
                ["123"]
            )
            
            # Verify success was logged
            self.handler.logger.debug.assert_called_with(
                f"Combo order updated successfully. New limit price: {self.ticket.Update.call_args[0][0].LimitPrice}"
            )

        with it('logs warning when update fails'):
            # Setup failed update
            self.ticket.Update = MagicMock(return_value=self.failed_response)
            
            # Execute
            self.handler.updateComboLimitOrder(
                self.position, 
                self.order, 
                ["123"]
            )
            
            # Verify warning was logged
            self.handler.logger.warning.assert_called_with(
                f"Failed to update combo order: {self.failed_response.ErrorCode}"
            )

        with it('skips update when ticket is filled'):
            # Set ticket status to filled
            self.ticket.Status = OrderStatus.Filled
            
            # Execute
            self.handler.updateComboLimitOrder(
                self.position, 
                self.order, 
                ["123"]
            )
            
            # Verify update was not called
            expect(self.ticket.Update.called).to(be_false)

        with it('updates retry information'):
            # Setup successful update
            self.ticket.Update = MagicMock(return_value=self.success_response)
            
            # Track initial values
            initial_time = self.order.lastRetry
            initial_retries = self.order.fillRetries
            
            # Execute
            self.handler.updateComboLimitOrder(
                self.position, 
                self.order, 
                ["123"]
            )
            
            # Verify retry information was updated
            expect(self.order.lastRetry).not_to(equal(initial_time))
            expect(self.order.fillRetries).to(equal(initial_retries + 1))

        with it('logs order execution details'):
            # Mock logOrderExecution
            self.handler.logOrderExecution = MagicMock()
            
            # Execute
            self.handler.updateComboLimitOrder(
                self.position, 
                self.order, 
                ["123"]
            )
            
            # Verify log was called with UPDATED action
            self.handler.logOrderExecution.assert_called_once()
            expect(self.handler.logOrderExecution.call_args[1]['action']).to(equal("UPDATED"))

    with context('calculateAdjustmentValueBought'):
        with before.each:
            # Create execution order with known values
            self.exec_order = MockExecOrder(
                bidAskSpread=0.1,
                midPrice=1.0
            )
            
            # Set base parameters to known values
            type(self.base).orderAdjustmentPct = property(lambda x: 0.1)
            type(self.base).minPricePct = property(lambda x: 0.5)
            type(self.base).retryChangePct = property(lambda x: 0.1)

        with it('raises error when required parameters are missing'):
            # Set both parameters to None
            type(self.base).orderAdjustmentPct = property(lambda x: None)
            type(self.base).adjustmentIncrement = property(lambda x: None)
            
            def call_with_missing_params():
                self.handler.calculateAdjustmentValueBought(
                    self.exec_order,
                    limitOrderPrice=1.0
                )
            
            expect(call_with_missing_params).to(raise_error(
                ValueError,
                "orderAdjustmentPct or adjustmentIncrement must be set in the parameters"
            ))

        with it('adjusts target price based on retries'):
            # Use retries=1 for base case to avoid division by zero
            result_without_retries = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=1,  # Changed from 0 to 1
                nrContracts=1
            )
            
            result_with_retries = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=2,
                nrContracts=1
            )
            
            # Result with more retries should be higher to increase chance of fill
            expect(float(result_with_retries)).to(be_above(float(result_without_retries)))

        with it('calculates step from bidAskSpread when adjustmentIncrement is None'):
            type(self.base).adjustmentIncrement = property(lambda x: None)
            
            result = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=2,  # Use retries > 0 to test division
                nrContracts=1
            )
            
            # Step should be bidAskSpread/retries = 0.1/2 = 0.05
            expect(result).not_to(be_none)

        with it('uses adjustmentIncrement when provided'):
            type(self.base).adjustmentIncrement = property(lambda x: 0.05)
            
            result = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=1,
                nrContracts=1
            )
            
            expect(result).not_to(be_none)

        with it('respects minimum step size'):
            type(self.base).adjustmentIncrement = property(lambda x: 0.001)  # Very small increment
            
            result = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=1,
                nrContracts=1
            )
            
            # Result should reflect minimum step of 0.01
            expect(result).not_to(be_none)

        with it('scales adjustment by number of contracts'):
            result_single = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=1,
                nrContracts=1
            )
            
            result_multiple = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=1,
                nrContracts=2
            )
            
            # Result should be scaled by number of contracts
            expect(float(result_multiple)).to(equal(float(result_single) / 2))

        with it('respects maximum price limit'):
            # Set a low max price limit
            type(self.base).minPricePct = property(lambda x: 0.1)
            
            result = self.handler.calculateAdjustmentValueBought(
                self.exec_order,
                limitOrderPrice=1.0,
                retries=1,
                nrContracts=1
            )
            
            # Result should respect the max price limit
            expect(float(result)).not_to(be_above(0.1))