#region imports
from AlgorithmImports import *
#endregion
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_resolution():
    return MagicMock(Minute="Minute", Hour="Hour", Daily="Daily")

@pytest.fixture
def mock_algorithm_imports(mock_resolution):
    mock_imports = MagicMock()
    mock_imports.Resolution = mock_resolution
    return mock_imports

@pytest.fixture(autouse=True)
def patch_algorithm_imports(mock_algorithm_imports):
    with patch.dict('sys.modules', {'AlgorithmImports': mock_algorithm_imports}):
        yield mock_algorithm_imports

@pytest.fixture
def mock_algorithm():
    return MagicMock()

@pytest.fixture
def mock_qc_data():
    return MagicMock()

@pytest.fixture
def mock_symbol():
    return MagicMock()

@pytest.fixture
def mock_resolution_class():
    class MockResolution:
        Minute = "Minute"
        Hour = "Hour"
        Daily = "Daily"
    return MockResolution

@pytest.fixture
def mocked_timer(patch_algorithm_imports):
    from Tools.Timer import Timer
    return Timer

@pytest.fixture
def mocked_logger(patch_algorithm_imports):
    from Tools.Logger import Logger
    return Logger
