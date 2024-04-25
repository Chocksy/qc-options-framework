from ..test_helper import add_project_root_to_sys_path, unittest, MagicMock
# add_project_root_to_sys_path()

from AlgorithmImports import *
from Alpha import Base

class TestBaseAlphaModel(unittest.TestCase):

    def setUp(self):
        # Create a mock context object
        self.context = MagicMock()
        self.context.IsWarmingUp = False
        self.context.Time = datetime(2021, 1, 6, 10, 0, 0)
        self.context.underlyingSymbol = "SPY"
        self.context.IsMarketOpen.return_value = True
        self.context.scheduleStartTime = time(9, 30, 0)
        self.context.scheduleStopTime = time(16, 0, 0)
        self.context.scheduleFrequency = timedelta(minutes=5)
        self.context.maxActivePositions = 1
        self.context.currentActivePositions = 0
        self.context.currentWorkingOrdersToOpen = 0
        self.context.dte = 0
        self.context.dteWindow = 0
        self.context.executionTimer = MagicMock()
        self.context.getOptionContracts.return_value = []
        self.context.expiryList = {}

        # Create an instance of the Base Alpha Model
        self.alpha_model = Base(self.context)

    def test_update(self):
        # Test that the Update method returns an empty list of insights
        data = MagicMock()
        insights = self.alpha_model.Update(self.context, data)
        self.assertIsInstance(insights, list)
        self.assertEqual(len(insights), 0)

    def test_scanner_check(self):
        # Test that the ScannerCheck method returns None when the market is closed
        self.context.IsMarketOpen.return_value = False
        data = MagicMock()
        result = self.alpha_model.ScannerCheck(data)
        self.assertIsNone(result)

        # Test that the ScannerCheck method returns None when the algorithm is warming up
        self.context.IsMarketOpen.return_value = True
        self.context.IsWarmingUp = True
        result = self.alpha_model.ScannerCheck(data)
        self.assertIsNone(result)

    def test_on_securities_changed(self):
        # Test that the OnSecuritiesChanged method doesn't raise any exception
        changes = MagicMock()
        try:
            self.alpha_model.OnSecuritiesChanged(self.context, changes)
        except Exception as e:
            self.fail(f"test_on_securities_changed raised an exception: {e}")

if __name__ == '__main__':
    unittest.main()
