from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, be_none, have_length, have_key
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta, time

# Import test helpers
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Alpha.Utils.Scanner import Scanner
    from Tests.mocks.algorithm_imports import (
        SecurityType, Resolution, OptionRight, Symbol,
        TradeBar, datetime, timedelta, time
    )

with description('Alpha.Utils.Scanner') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            # Setup basic test environment
            self.algorithm = Factory.create_algorithm()
            
            # Add required attributes for Scanner
            self.algorithm.executionTimer = MagicMock(
                start=MagicMock(),
                stop=MagicMock()
            )
            self.algorithm.logLevel = 0
            self.algorithm.lastOpenedDttm = None
            self.algorithm.recentlyClosedDTE = []
            self.algorithm.openPositions = {}
            self.algorithm.allPositions = {}
            self.algorithm.workingOrders = {}
            self.algorithm.performance = MagicMock(OnUpdate=MagicMock())
            self.algorithm.dataHandler = MagicMock(getOptionContracts=MagicMock())
            
            # Create base mock with required attributes
            self.base = MagicMock()
            self.base.name = "TestStrategy"
            self.base.nameTag = "TestStrategy"
            self.base.underlyingSymbol = "SPX"
            self.base.dte = 30
            self.base.dteWindow = 5
            self.base.useFurthestExpiry = True
            self.base.dynamicDTESelection = False
            self.base.allowMultipleEntriesPerExpiry = False
            self.base.maxActivePositions = 1
            self.base.maxOpenPositions = 1
            self.base.scheduleStartTime = time(9, 30)
            self.base.scheduleStopTime = time(16, 0)
            self.base.scheduleFrequency = timedelta(minutes=5)
            self.base.dataHandler = MagicMock()
            
            # Create scanner instance
            self.scanner = Scanner(self.algorithm, self.base)
            
            # Mock common methods
            self.algorithm.IsWarmingUp = False
            self.algorithm.IsMarketOpen = MagicMock(return_value=True)
            self.algorithm.Time = datetime.now().replace(
                hour=10, minute=0, second=0, microsecond=0
            )

    with context('isMarketClosed'):
        with it('returns True when algorithm is warming up'):
            self.algorithm.IsWarmingUp = True
            expect(self.scanner.isMarketClosed()).to(be_true)
            
        with it('returns True when market is closed'):
            self.algorithm.IsMarketOpen.return_value = False
            expect(self.scanner.isMarketClosed()).to(be_true)
            
        with it('returns False when market is open and not warming up'):
            self.algorithm.IsWarmingUp = False
            self.algorithm.IsMarketOpen.return_value = True
            expect(self.scanner.isMarketClosed()).to(be_false)

    with context('isWithinScheduledTimeWindow'):
        with before.each:
            self.base.scheduleStartTime = time(9, 30)
            self.base.scheduleStopTime = time(16, 0)
            self.base.scheduleFrequency = timedelta(minutes=5)
            
        with it('returns False before schedule start time'):
            self.algorithm.Time = datetime.now().replace(hour=9, minute=0)
            expect(self.scanner.isWithinScheduledTimeWindow()).to(be_false)
            
        with it('returns False after schedule stop time'):
            self.algorithm.Time = datetime.now().replace(hour=16, minute=30)
            expect(self.scanner.isWithinScheduledTimeWindow()).to(be_false)
            
        with it('returns True at correct schedule interval'):
            self.algorithm.Time = datetime.now().replace(hour=10, minute=0)
            expect(self.scanner.isWithinScheduledTimeWindow()).to(be_true)
            
        with it('returns False between schedule intervals'):
            self.algorithm.Time = datetime.now().replace(hour=10, minute=2)
            expect(self.scanner.isWithinScheduledTimeWindow()).to(be_false)

    with context('position limits'):
        with before.each:
            self.base.maxActivePositions = 2
            self.base.maxOpenPositions = 1
            self.base.nameTag = "TestStrategy"
            
        with context('hasReachedMaxActivePositions'):
            with it('returns True when max active positions reached'):
                # Create mock positions with matching strategy tag
                self.algorithm.openPositions = {"pos1": "order1", "pos2": "order2"}
                self.algorithm.allPositions = {
                    "order1": MagicMock(strategyTag="TestStrategy"),
                    "order2": MagicMock(strategyTag="TestStrategy")
                }
                expect(self.scanner.hasReachedMaxActivePositions()).to(be_true)
                
            with it('returns False when below max active positions'):
                self.algorithm.openPositions = {"pos1": "order1"}
                self.algorithm.allPositions = {
                    "order1": MagicMock(strategyTag="TestStrategy")
                }
                expect(self.scanner.hasReachedMaxActivePositions()).to(be_false)
                
            with it('ignores positions from other strategies'):
                self.algorithm.openPositions = {"pos1": "order1", "pos2": "order2"}
                self.algorithm.allPositions = {
                    "order1": MagicMock(strategyTag="TestStrategy"),
                    "order2": MagicMock(strategyTag="OtherStrategy")
                }
                expect(self.scanner.hasReachedMaxActivePositions()).to(be_false)
                
        with context('hasReachedMaxOpenPositions'):
            with it('returns True when max open positions reached'):
                self.algorithm.workingOrders = {
                    "order1": MagicMock(strategyTag="TestStrategy")
                }
                expect(self.scanner.hasReachedMaxOpenPositions()).to(be_true)
                
            with it('returns False when below max open positions'):
                self.algorithm.workingOrders = {}
                expect(self.scanner.hasReachedMaxOpenPositions()).to(be_false)

    with context('filterByExpiry'):
        with before.each:
            self.target_expiry = datetime.now() + timedelta(days=30)
            self.chain = [
                MagicMock(Expiry=self.target_expiry),
                MagicMock(Expiry=self.target_expiry + timedelta(days=30)),
                MagicMock(Expiry=self.target_expiry - timedelta(days=30))
            ]
            
        with it('filters contracts by expiry date'):
            filtered = self.scanner.filterByExpiry(self.chain, self.target_expiry)
            expect(filtered).to(have_length(1))
            expect(filtered[0].Expiry).to(equal(self.target_expiry))
            
        with it('returns all contracts when no expiry specified'):
            filtered = self.scanner.filterByExpiry(self.chain)
            expect(filtered).to(have_length(3))
            
        with it('computes Greeks when requested'):
            self.scanner.bsm.setGreeks = MagicMock()
            self.scanner.filterByExpiry(self.chain, computeGreeks=True)
            self.scanner.bsm.setGreeks.assert_called_once()

    with context('syncExpiryList'):
        with before.each:
            self.current_date = datetime.now().date()
            current_time = datetime.now()
            
            # Create proper mock expiries that behave like datetime with comparison support
            def create_mock_expiry(days):
                actual_date = current_time + timedelta(days=days)
                mock_expiry = MagicMock(spec=datetime)
                mock_expiry.date.return_value = actual_date.date()
                # Add comparison methods
                mock_expiry.__lt__ = lambda self, other: actual_date < other._actual_date
                mock_expiry.__gt__ = lambda self, other: actual_date > other._actual_date
                mock_expiry.__eq__ = lambda self, other: actual_date == other._actual_date
                mock_expiry._actual_date = actual_date  # Store for comparisons
                return mock_expiry
            
            # Create mocks with proper comparison support
            mock_expiry1 = create_mock_expiry(28)  # Within range (28 days)
            mock_expiry2 = create_mock_expiry(32)  # Within range (32 days)
            mock_expiry3 = create_mock_expiry(45)  # Outside range (45 days)
            
            # Create contracts with expiries that fall within the DTE range (25-35 days)
            self.chain = [
                MagicMock(Expiry=mock_expiry1),
                MagicMock(Expiry=mock_expiry2),
                MagicMock(Expiry=mock_expiry3)
            ]
            
            # Set DTE range to ensure two contracts fall within it
            self.base.dte = 35  # Max DTE
            self.base.dteWindow = 10  # Window size, so range is 25-35 days
            
        with it('updates expiry list for new date'):
            self.scanner.syncExpiryList(self.chain)
            expect(self.scanner.expiryList).to(have_key(self.current_date))
            expect(self.scanner.expiryList[self.current_date]).to(have_length(2))
            
        with it('reuses existing expiry list for same date'):
            self.scanner.expiryList[self.current_date] = ["existing"]
            self.scanner.syncExpiryList(self.chain)
            expect(self.scanner.expiryList[self.current_date]).to(equal(["existing"]))
            
        with it('filters expiries within DTE range'):
            # Change DTE range to only include one contract
            self.base.dte = 30
            self.base.dteWindow = 5  # Range becomes 25-30 days
            self.scanner.syncExpiryList(self.chain)
            expiries = self.scanner.expiryList[self.current_date]
            expect(expiries).to(have_length(1))

    with context('Call'):
        with before.each:
            self.scanner.isMarketClosed = MagicMock(return_value=False)
            self.scanner.isWithinScheduledTimeWindow = MagicMock(return_value=True)
            self.scanner.hasReachedMaxActivePositions = MagicMock(return_value=False)
            self.scanner.hasReachedMaxOpenPositions = MagicMock(return_value=False)
            self.scanner.Filter = MagicMock(return_value=([], None))
            self.base.dataHandler = MagicMock()
            
        with it('returns None when market is closed'):
            self.scanner.isMarketClosed.return_value = True
            result, tag = self.scanner.Call(None)
            expect(result).to(be_none)
            expect(tag).to(be_none)
            
        with it('returns None when not in time window'):
            self.scanner.isWithinScheduledTimeWindow.return_value = False
            result, tag = self.scanner.Call(None)
            expect(result).to(be_none)
            expect(tag).to(be_none)
            
        with it('returns None when max positions reached'):
            self.scanner.hasReachedMaxActivePositions.return_value = True
            result, tag = self.scanner.Call(None)
            expect(result).to(be_none)
            expect(tag).to(be_none)
            
        with it('processes chain when conditions are met'):
            # Create a mock expiry that behaves like a datetime
            mock_expiry = MagicMock(spec=datetime)
            mock_expiry.date.return_value = (datetime.now() + timedelta(days=30)).date()
            
            mock_chain = [
                MagicMock(
                    Expiry=mock_expiry,  # Use the mock instead of real datetime
                    Strike=100
                )
            ]
            
            self.base.dataHandler.getOptionContracts.return_value = mock_chain
            self.scanner.Call(None)
            self.scanner.Filter.assert_called_once_with(mock_chain)

    with context('Filter'):
        with before.each:
            # Create chain with proper Expiry mocks
            current_date = datetime.now().date()
            expiry_date = datetime.now() + timedelta(days=30)
            expiry_str = expiry_date.strftime("%Y-%m-%d")
            
            # Create a proper mock that behaves like a datetime
            mock_expiry = MagicMock(spec=datetime)
            mock_expiry.date.return_value = expiry_date.date()
            mock_expiry.__sub__ = lambda self, other: timedelta(days=30)
            mock_expiry.strftime = MagicMock(return_value=expiry_str)
            
            self.chain = [
                MagicMock(
                    Expiry=mock_expiry,
                    Strike=100
                )
            ]
            
            # Create a mock list instead of trying to modify a real list
            mock_expiries = MagicMock()
            mock_expiries.__iter__ = lambda x: iter([mock_expiry])
            mock_expiries.__len__ = lambda x: 1
            mock_expiries.__getitem__ = lambda x, i: mock_expiry
            
            self.scanner.expiryList = {
                current_date: mock_expiries
            }
            self.algorithm.lastOpenedDttm = None
            self.algorithm.recentlyClosedDTE = []
            
            # Mock the parameter method to return None by default
            self.base.parameter = MagicMock(return_value=None)
            
        with it('respects minimum trade schedule distance'):
            self.base.parameter = MagicMock(return_value=timedelta(hours=1))
            self.algorithm.lastOpenedDttm = datetime.now() - timedelta(minutes=30)
            result, tag = self.scanner.Filter(self.chain)
            expect(result).to(be_none)
            expect(tag).to(be_none)
            
        with it('handles dynamic DTE selection'):
            self.base.dynamicDTESelection = True
            self.algorithm.recentlyClosedDTE = [
                {"closeDte": 30, "orderTag": "test_tag"}
            ]
            
            # Mock sorted to return our mock_expiry
            mock_sorted = MagicMock(return_value=[self.chain[0].Expiry])
            with patch('builtins.sorted', mock_sorted):
                result, tag = self.scanner.Filter(self.chain)
                expect(tag).to(equal("test_tag"))
            
        with it('respects allowMultipleEntriesPerExpiry setting'):
            self.base.allowMultipleEntriesPerExpiry = False
            expiry_str = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            
            # Create mock position with matching strategy tag and expiry
            mock_position = MagicMock(
                strategyTag="TestStrategy",  # Match the base.nameTag we set in before.each
                expiryStr=expiry_str
            )
            
            # Set up open positions
            self.algorithm.openPositions = {"pos1": "order1"}
            self.algorithm.allPositions = {"order1": mock_position}
            
            # The chain's Expiry is already mocked with strftime in before.each
            result, tag = self.scanner.Filter(self.chain)
            expect(result).to(be_none)