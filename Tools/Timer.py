#region imports
from AlgorithmImports import *
#endregion
import time as timer
import math
from datetime import timedelta

class Timer:

    performanceTemplate = {
        "calls": 0.0,
        "elapsedMin": float('Inf'),
        "elapsedMean": None,
        "elapsedMax": float('-Inf'),
        "elapsedTotal": 0.0,
        "elapsedLast": None,
        "startTime": None,
    }

    def __init__(self, context):
        self.context = context
        self.performance = {}

    def start(self, methodName=None):
        # Get the name of the calling method
        methodName = methodName or sys._getframe(1).f_code.co_name
        # Get current performance stats
        performance = self.performance.get(methodName, Timer.performanceTemplate.copy())
        # Get the startTime
        performance["startTime"] = timer.perf_counter()
        # Save it back in the dictionary
        self.performance[methodName] = performance

    def stop(self, methodName=None):
        # Get the name of the calling method
        methodName = methodName or sys._getframe(1).f_code.co_name
        # Get current performance stats
        performance = self.performance.get(methodName)
        # Compute the elapsed
        elapsed = timer.perf_counter() - performance["startTime"]
        # Update the stats
        performance["calls"] += 1
        performance["elapsedLast"] = elapsed
        performance["elapsedMin"] = min(performance["elapsedMin"], elapsed)
        performance["elapsedMax"] = max(performance["elapsedMax"], elapsed)
        performance["elapsedTotal"] += elapsed
        performance["elapsedMean"] = performance["elapsedTotal"]/performance["calls"]

    def showStats(self, methodName=None):
        methods = methodName or self.performance.keys()
        total_elapsed = 0.0  # Initialize total elapsed time
        for method in methods:
            performance = self.performance.get(method)
            if performance:
                self.context.Log(f"Execution Stats ({method}):")
                for key in performance:
                    if key != "startTime":
                        if key == "calls" or performance[key] == None:
                            value = performance[key]
                        elif math.isinf(performance[key]):
                            value = None
                        else:
                            value = timedelta(seconds=performance[key])
                        self.context.Log(f"  --> {key}:{value}")
                total_elapsed += performance.get("elapsedTotal", 0)  # Accumulate elapsedTotal
            else:
                self.context.Log(f"There are no execution stats available for method {method}!")
        # Print the total elapsed time over all methods
        self.context.Log("Summary:")
        self.context.Log(f"  --> elapsedTotal: {timedelta(seconds=total_elapsed)}")
