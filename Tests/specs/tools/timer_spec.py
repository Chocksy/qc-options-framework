from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none, be_above
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

with patch_imports()[0], patch_imports()[1]:
    from Tools.Timer import Timer
    from AlgorithmImports import timedelta

with description('Timer') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.timer = Timer(self.algorithm)

    with context('initialization'):
        with it('initializes with empty performance dictionary'):
            expect(self.timer.performance).to(equal({}))
            expect(self.timer.context).to(equal(self.algorithm))

    with context('start/stop timing'):
        with it('tracks method execution time correctly'):
            with patch('time.perf_counter') as mock_timer:
                # Simulate elapsed time of 2 seconds
                mock_timer.side_effect = [10.0, 12.0]  # start and stop times
                
                self.timer.start('test_method')
                self.timer.stop('test_method')
                
                perf = self.timer.performance['test_method']
                expect(perf['calls']).to(equal(1.0))
                expect(perf['elapsedLast']).to(equal(2.0))
                expect(perf['elapsedTotal']).to(equal(2.0))
                expect(perf['elapsedMean']).to(equal(2.0))
                expect(perf['elapsedMin']).to(equal(2.0))
                expect(perf['elapsedMax']).to(equal(2.0))

        with it('tracks multiple calls to same method'):
            with patch('time.perf_counter') as mock_timer:
                # Simulate two calls with different elapsed times
                mock_timer.side_effect = [10.0, 11.0, 20.0, 22.0]
                
                self.timer.start('test_method')
                self.timer.stop('test_method')
                self.timer.start('test_method')
                self.timer.stop('test_method')
                
                perf = self.timer.performance['test_method']
                expect(perf['calls']).to(equal(2.0))
                expect(perf['elapsedTotal']).to(equal(3.0))
                expect(perf['elapsedMean']).to(equal(1.5))
                expect(perf['elapsedMin']).to(equal(1.0))
                expect(perf['elapsedMax']).to(equal(2.0))

    with context('showStats'):
        with it('displays stats for single method'):
            with patch('time.perf_counter') as mock_timer:
                mock_timer.side_effect = [10.0, 12.0]
                
                self.timer.start('test_method')
                self.timer.stop('test_method')
                self.timer.showStats('test_method')
                
                # Verify Log was called with appropriate messages
                self.algorithm.Log.assert_called()

        with it('displays stats for all methods when no method specified'):
            with patch('time.perf_counter') as mock_timer:
                mock_timer.side_effect = [10.0, 12.0, 20.0, 23.0]
                
                self.timer.start('method1')
                self.timer.stop('method1')
                self.timer.start('method2')
                self.timer.stop('method2')
                
                self.timer.showStats()
                
                # Verify Log was called multiple times including summary
                calls = self.algorithm.Log.call_args_list
                # Should have multiple calls: stats for each method + summary
                expect(len(calls)).to(be_above(3))  # At least 4 calls expected:
                                                   # - Header for method1
                                                   # - Stats for method1
                                                   # - Header for method2
                                                   # - Stats for method2
                                                   # - Summary header
                                                   # - Total elapsed time

        with it('handles non-existent method gracefully'):
            self.timer.showStats('non_existent_method')
            expected_calls = [
                call('Summary:'),
                call('  --> elapsedTotal: 0:00:00')
            ]
            self.algorithm.Log.assert_has_calls(expected_calls, any_order=True)