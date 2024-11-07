from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key
from unittest.mock import patch, MagicMock
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Use patch_imports to get access to datetime through AlgorithmImports
with patch_imports()[0], patch_imports()[1]:
    from AlgorithmImports import datetime, timedelta, Resolution, OrderStatus
    from Tools.Performance import Performance

# Create a fixed datetime for testing
FIXED_DATE = datetime(2024, 1, 1)

with description('Performance') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            # Create a mock datetime object
            mock_dt = MagicMock()
            mock_dt.now.return_value = FIXED_DATE
            mock_dt.side_effect = datetime
            
            # Use ModuleMocks for patching
            with patch.dict('sys.modules', ModuleMocks.get_all()):
                with patch('Tools.Performance.datetime', mock_dt):
                    self.algorithm = Factory.create_algorithm()
                    self.algorithm.logger = MagicMock()
                    self.algorithm.Time = FIXED_DATE
                    self.performance = Performance(self.algorithm)
                    self.test_symbol = Factory.create_symbol()

    with context('endOfDay'):
        with it('tracks daily statistics correctly'):
            mock_dt = MagicMock()
            mock_dt.now.return_value = FIXED_DATE
            mock_dt.side_effect = datetime
            
            # Use ModuleMocks for patching
            with patch.dict('sys.modules', ModuleMocks.get_all()):
                with patch('Tools.Performance.datetime', mock_dt):
                    self.performance.endOfDay(self.test_symbol)
                    today = FIXED_DATE.date()
                    
                    expect(self.performance.tracking).to(have_key(today))
                    expect(self.performance.tracking[today]).to(have_key(str(self.test_symbol)))
                    
                    day_stats = self.performance.tracking[today][str(self.test_symbol)]
                    expect(day_stats).to(have_key('Time'))
                    expect(day_stats).to(have_key('Portfolio'))
                    expect(day_stats).to(have_key('Invested'))
                    expect(day_stats).to(have_key('Seen'))
                    expect(day_stats).to(have_key('Traded'))
                    expect(day_stats).to(have_key('Chains'))

    with context('OnOrderEvent'):
        with it('tracks filled orders'):
            order_event = MagicMock(
                Status=OrderStatus.Filled,
                Symbol=self.test_symbol,
                Quantity=100
            )
            self.performance.OnOrderEvent(order_event)
            expect(self.performance.tradedSymbols).to(contain(self.test_symbol))
            expect(self.performance.tradedToday).to(be_true)

        with it('handles unwound positions'):
            order_event = MagicMock(
                Status=OrderStatus.Filled,
                Symbol=self.test_symbol,
                Quantity=-100
            )
            self.performance.OnOrderEvent(order_event)
            expect(self.performance.tradedToday).to(be_false)

    with context('OnUpdate'):
        with it('tracks option chains'):
            # Create mock option contracts
            chain = [
                MagicMock(Symbol=Factory.create_symbol("OPT1")),
                MagicMock(Symbol=Factory.create_symbol("OPT2"))
            ]
            
            # Create the data mock with OptionChains that behaves like a KeyValuePair collection
            data = MagicMock()
            data.OptionChains = MagicMock()
            
            # Make OptionChains iterable and return KeyValuePair-like objects
            kvp_mock = MagicMock()
            kvp_mock.Value = chain
            data.OptionChains.__iter__ = MagicMock(return_value=iter([kvp_mock]))
            
            self.performance.OnUpdate(data)
            expect(len(self.performance.chainSymbols)).to(equal(2))
            expect(len(self.performance.seenSymbols)).to(equal(2))

    with context('show'):
        with it('displays performance data in CSV format'):
            self.performance.endOfDay(self.test_symbol)
            self.performance.show(csv=True)
            self.algorithm.Log.assert_called()

        with it('displays performance data in regular format'):
            self.performance.endOfDay(self.test_symbol)
            self.performance.show(csv=False)
            self.algorithm.Log.assert_called() 