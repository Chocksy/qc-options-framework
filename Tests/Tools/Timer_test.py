#region imports
from AlgorithmImports import *
#endregion
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import pytest
from unittest.mock import patch, MagicMock, call
import time

def test_timer_initialization(mock_algorithm, mocked_timer):
    timer = mocked_timer(mock_algorithm)
    assert timer.context == mock_algorithm
    assert timer.performance == {}

def test_timer_start(mock_algorithm, mocked_timer):
    timer = mocked_timer(mock_algorithm)
    with patch('time.perf_counter', return_value=100.0):
        timer.start('test_method')
    assert 'test_method' in timer.performance
    assert timer.performance['test_method']['startTime'] == 100.0

def test_timer_stop(mock_algorithm, mocked_timer):
    timer = mocked_timer(mock_algorithm)
    timer.performance['test_method'] = timer.performanceTemplate.copy()
    timer.performance['test_method']['startTime'] = 100.0
    with patch('time.perf_counter', return_value=150.0):
        timer.stop('test_method')
    
    performance = timer.performance['test_method']
    assert performance['calls'] == 1
    assert performance['elapsedLast'] == 50.0
    assert performance['elapsedMin'] == 50.0
    assert performance['elapsedMax'] == 50.0
    assert performance['elapsedTotal'] == 50.0
    assert performance['elapsedMean'] == 50.0

def test_timer_show_stats(mock_algorithm, mocked_timer):
    timer = mocked_timer(mock_algorithm)
    timer.performance['method1'] = {
        'calls': 2,
        'elapsedMin': 10.0,
        'elapsedMean': 15.0,
        'elapsedMax': 20.0,
        'elapsedTotal': 30.0,
        'elapsedLast': 15.0,
        'startTime': None
    }
    timer.performance['method2'] = {
        'calls': 1,
        'elapsedMin': 5.0,
        'elapsedMean': 5.0,
        'elapsedMax': 5.0,
        'elapsedTotal': 5.0,
        'elapsedLast': 5.0,
        'startTime': None
    }
    
    timer.showStats()
    
    # Check that Log method was called with the correct arguments
    expected_calls = [
        call("Execution Stats (method1):"),
        call("  --> calls:2"),
        call("  --> elapsedMin:0:00:10"),
        call("  --> elapsedMean:0:00:15"),
        call("  --> elapsedMax:0:00:20"),
        call("  --> elapsedTotal:0:00:30"),
        call("  --> elapsedLast:0:00:15"),
        call("Execution Stats (method2):"),
        call("  --> calls:1"),
        call("  --> elapsedMin:0:00:05"),
        call("  --> elapsedMean:0:00:05"),
        call("  --> elapsedMax:0:00:05"),
        call("  --> elapsedTotal:0:00:05"),
        call("  --> elapsedLast:0:00:05"),
        call("Summary:"),
        call("  --> elapsedTotal: 0:00:35")
    ]
    
    mock_algorithm.Log.assert_has_calls(expected_calls, any_order=True)

def test_timer_multiple_methods(mock_algorithm, mocked_timer):
    timer = mocked_timer(mock_algorithm)
    with patch('time.perf_counter') as mock_time:
        mock_time.side_effect = [100.0, 150.0, 200.0, 300.0]
        
        timer.start('method1')
        timer.stop('method1')
        timer.start('method2')
        timer.stop('method2')
    
    assert 'method1' in timer.performance
    assert 'method2' in timer.performance
    assert timer.performance['method1']['elapsedTotal'] == 50.0
    assert timer.performance['method2']['elapsedTotal'] == 100.0