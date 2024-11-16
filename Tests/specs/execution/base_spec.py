from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none, raise_error
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta

# Import test helpers
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Execution.Base import Base
    from Tests.mocks.algorithm_imports import (
        SecurityType, Resolution, OptionRight, Symbol,
        TradeBar, PortfolioTarget, datetime, timedelta,
        List, SecurityChanges, SecuritiesDict, ExecutionModel,
        PortfolioTargetCollection
    )

with description('Execution.Base') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Mock common attributes
            self.algorithm.logger = MagicMock(debug=MagicMock())
            self.algorithm.debug = MagicMock()
            self.algorithm.executionTimer = MagicMock(start=MagicMock(), stop=MagicMock())
            self.algorithm.Portfolio = MagicMock()
            self.algorithm.Securities = SecuritiesDict()
            self.algorithm.Time = datetime.now()
            self.algorithm.workingOrders = {}
            
            # Mock structure
            self.algorithm.structure = MagicMock()
            self.algorithm.structure.AddConfiguration = MagicMock()
            self.algorithm.structure.checkOpenPositions = MagicMock()
            
            # Create Base instance
            self.base = Base(self.algorithm)
            
            # Mock handlers
            self.base.marketOrderHandler = MagicMock()
            self.base.limitOrderHandler = MagicMock()

    with context('initialization'):
        with it('initializes with default parameters'):
            expect(self.base.context).to(equal(self.algorithm))
            expect(self.base.targetsCollection).not_to(be_none)
            expect(self.base.contractUtils).not_to(be_none)
            expect(self.base.logger).not_to(be_none)
            
            # Verify default parameters were merged
            self.algorithm.structure.AddConfiguration.assert_called_once()
            call_kwargs = self.algorithm.structure.AddConfiguration.call_args.kwargs
            expect(call_kwargs).to(have_key('retryChangePct'))
            expect(call_kwargs).to(have_key('minPricePct'))
            expect(call_kwargs).to(have_key('speedOfFill'))

        with it('merges parameters correctly'):
            class CustomBase(Base):
                PARAMETERS = {
                    'retryChangePct': 2.0,
                    'customParam': 'test'
                }
            
            custom_base = CustomBase(self.algorithm)
            merged_params = custom_base.getMergedParameters()
            
            expect(merged_params['retryChangePct']).to(equal(2.0))
            expect(merged_params['customParam']).to(equal('test'))
            expect(merged_params).to(have_key('minPricePct'))

    with context('Execute'):
        with before.each:
            self.mock_targets = [MagicMock()]
            self.mock_working_order = MagicMock(
                orderId="order1",
                fillRetries=0,
                useLimitOrder=True,
                lastRetry=None
            )
            self.mock_position = MagicMock()
            
            # Setup algorithm with working order
            self.algorithm.workingOrders = {"tag1": self.mock_working_order}
            self.algorithm.allPositions = {"order1": self.mock_position}
            
            # Mock parameter to return integer for maxRetries
            self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                'maxRetries': 5,
                'speedOfFill': 'Patient'
            }.get(key, default))

        with context('speed of fill conditions'):
            with it('executes every minute for Fast speed'):
                # Override speedOfFill parameter
                self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                    'maxRetries': 5,
                    'speedOfFill': 'Fast'
                }.get(key, default))
                
                self.algorithm.Time = datetime.now().replace(minute=1)
                self.base.Execute(self.algorithm, self.mock_targets)
                self.algorithm.structure.checkOpenPositions.assert_called_once()

            with it('executes every 3 minutes for Normal speed'):
                # Override speedOfFill parameter
                self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                    'maxRetries': 5,
                    'speedOfFill': 'Normal'
                }.get(key, default))
                
                # Test non-execution minute
                self.algorithm.Time = datetime.now().replace(minute=1)
                self.base.Execute(self.algorithm, self.mock_targets)
                expect(self.algorithm.structure.checkOpenPositions.call_count).to(equal(0))
                
                # Test execution minute
                self.algorithm.Time = datetime.now().replace(minute=3)
                self.base.Execute(self.algorithm, self.mock_targets)
                self.algorithm.structure.checkOpenPositions.assert_called_once()

            with it('executes every 5 minutes for Patient speed'):
                # Override speedOfFill parameter
                self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                    'maxRetries': 5,
                    'speedOfFill': 'Patient'
                }.get(key, default))
                
                # Test non-execution minute
                self.algorithm.Time = datetime.now().replace(minute=2)
                self.base.Execute(self.algorithm, self.mock_targets)
                expect(self.algorithm.structure.checkOpenPositions.call_count).to(equal(0))
                
                # Test execution minute
                self.algorithm.Time = datetime.now().replace(minute=5)
                self.base.Execute(self.algorithm, self.mock_targets)
                self.algorithm.structure.checkOpenPositions.assert_called_once()

        with context('order processing'):
            with before.each:
                # Set speedOfFill to Fast so it executes every minute
                self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                    'maxRetries': 5,
                    'speedOfFill': 'Fast'  # This ensures execution every minute
                }.get(key, default))
                
                # Set time to ensure execution
                self.algorithm.Time = datetime.now().replace(minute=1)

            with it('skips orders exceeding max retries'):
                self.mock_working_order.fillRetries = 6
                
                self.base.Execute(self.algorithm, self.mock_targets)
                expect(self.base.limitOrderHandler.call.call_count).to(equal(0))
                expect(self.base.marketOrderHandler.call.call_count).to(equal(0))

            with it('processes limit orders'):
                self.mock_working_order.useLimitOrder = True
                self.mock_working_order.fillRetries = 0  # Ensure we're under max retries
                
                self.base.Execute(self.algorithm, self.mock_targets)
                self.base.limitOrderHandler.call.assert_called_once_with(
                    self.mock_position, 
                    self.mock_working_order
                )

            with it('processes market orders'):
                self.mock_working_order.useLimitOrder = False
                self.mock_working_order.fillRetries = 0  # Ensure we're under max retries
                
                self.base.Execute(self.algorithm, self.mock_targets)
                self.base.marketOrderHandler.call.assert_called_once_with(
                    self.mock_position, 
                    self.mock_working_order
                )

        with it('clears fulfilled targets'):
            # Set speedOfFill to Fast for consistent execution
            self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                'maxRetries': 5,
                'speedOfFill': 'Fast'
            }.get(key, default))
            
            self.algorithm.Time = datetime.now().replace(minute=1)
            self.base.targetsCollection.ClearFulfilled = MagicMock()
            
            self.base.Execute(self.algorithm, self.mock_targets)
            self.base.targetsCollection.ClearFulfilled.assert_called_once_with(self.algorithm)

        with it('updates charts after execution'):
            # Set speedOfFill to Fast for consistent execution
            self.base.parameter = MagicMock(side_effect=lambda key, default=None: {
                'maxRetries': 5,
                'speedOfFill': 'Fast'
            }.get(key, default))
            
            self.algorithm.Time = datetime.now().replace(minute=1)
            self.algorithm.charting = MagicMock()
            
            self.base.Execute(self.algorithm, self.mock_targets)
            self.algorithm.charting.updateCharts.assert_called_once() 