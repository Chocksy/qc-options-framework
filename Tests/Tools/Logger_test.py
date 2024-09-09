#region imports
from AlgorithmImports import *
#endregion
import pytest
from unittest.mock import patch, call
import pandas as pd

@pytest.fixture
def logger(mock_algorithm, mocked_logger):
    return mocked_logger(mock_algorithm, className="TestClass", logLevel=3)

def test_logger_initialization(mock_algorithm, mocked_logger):
    logger = mocked_logger(mock_algorithm, className="TestClass", logLevel=3)
    assert logger.context == mock_algorithm
    assert logger.className == "TestClass"
    assert logger.logLevel == 3

def test_log_method(logger, mock_algorithm):
    with patch('sys._getframe') as mock_frame:
        mock_frame.return_value.f_code.co_name = 'test_function'
        logger.Log("Test message", trsh=2)
    
    mock_algorithm.Log.assert_called_once_with(" INFO -> TestClass.test_function: Test message")

@pytest.mark.parametrize("method,expected_prefix", [
    ("error", "ERROR"),
    ("warning", "WARNING"),
    ("info", "INFO"),
    ("debug", "DEBUG"),
    ("trace", "TRACE")
])
def test_log_levels(logger, mock_algorithm, method, expected_prefix):
    with patch('sys._getframe') as mock_frame:
        mock_frame.return_value.f_code.co_name = 'test_function'
        getattr(logger, method)("Test message")
    
    mock_algorithm.Log.assert_called_once_with(f" {expected_prefix} -> TestClass.test_function: Test message")

def test_log_level_filtering(mock_algorithm, mocked_logger):
    logger = mocked_logger(mock_algorithm, className="TestClass", logLevel=2)
    
    with patch('sys._getframe') as mock_frame:
        mock_frame.return_value.f_code.co_name = 'test_function'
        logger.error("Error message")
        logger.warning("Warning message")
        logger.info("Info message")
        logger.debug("Debug message")
        logger.trace("Trace message")
    
    assert mock_algorithm.Log.call_count == 3
    mock_algorithm.Log.assert_has_calls([
        call(" ERROR -> TestClass.test_function: Error message"),
        call(" WARNING -> TestClass.test_function: Warning message"),
        call(" INFO -> TestClass.test_function: Info message")
    ])

def test_dataframe_logging(logger, mock_algorithm):
    test_data = [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25}
    ]
    expected_output = "\n  name  age\nAlice   30\n  Bob   25"
    
    with patch('sys._getframe') as mock_frame:
        mock_frame.return_value.f_code.co_name = 'test_function'
        with patch('pandas.DataFrame.to_string', return_value=expected_output):
            logger.dataframe(test_data)
    
    mock_algorithm.Log.assert_called_once_with(f" INFO -> TestClass.test_function: {expected_output}")

def test_dataframe_logging_empty_data(logger, mock_algorithm):
    test_data = []
    
    logger.dataframe(test_data)
    
    mock_algorithm.Log.assert_not_called()

def test_dataframe_logging_dict_input(logger, mock_algorithm):
    test_data = {'name': ['Alice', 'Bob'], 'age': [30, 25]}
    expected_output = "\n  name  age\nAlice   30\n  Bob   25"
    
    with patch('sys._getframe') as mock_frame:
        mock_frame.return_value.f_code.co_name = 'test_function'
        with patch('pandas.DataFrame.to_string', return_value=expected_output):
            logger.dataframe(test_data)
    
    mock_algorithm.Log.assert_called_once_with(f" INFO -> TestClass.test_function: {expected_output}")