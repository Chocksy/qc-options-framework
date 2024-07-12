#region imports
from AlgorithmImports import *
#endregion
import sys
import pandas as pd
from collections import deque

class Logger:
    def __init__(self, context, className=None, logLevel=0, buffer_size=100):
        self.context = context
        self.className = className
        self.logLevel = logLevel
        self.log_buffer = deque(maxlen=buffer_size)
        self.current_pattern = []
        self.pattern_count = 0

    def Log(self, msg, trsh=0):
        if self.logLevel < trsh:
            return

        className = f"{self.className}." if self.className else ""
        prefix = ["ERROR", "WARNING", "INFO", "DEBUG", "TRACE"][min(trsh, 4)]
        log_msg = f"{prefix} -> {className}{sys._getframe(2).f_code.co_name}: {msg}"

        self.process_log(log_msg)

    def process_log(self, log_msg):
        if not self.current_pattern:
            self.print_log(log_msg)
            self.current_pattern.append(log_msg)
        else:
            pattern_index = self.find_pattern_start(log_msg)
            if pattern_index == -1:
                self.print_pattern()
                self.print_log(log_msg)
                self.current_pattern.append(log_msg)
            else:
                if pattern_index == 0:
                    self.pattern_count += 1
                else:
                    self.print_pattern()
                    self.print_log("--- New log cycle starts ---")
                    self.current_pattern = self.current_pattern[pattern_index:]
                    self.pattern_count = 1

        self.log_buffer.append(log_msg)

    def find_pattern_start(self, log_msg):
        for i in range(len(self.current_pattern)):
            if log_msg == self.current_pattern[i]:
                if self.is_pattern_repeating(i):
                    return i
        return -1

    def is_pattern_repeating(self, start_index):
        pattern_length = len(self.current_pattern) - start_index
        if len(self.log_buffer) < pattern_length:
            return False
        return list(self.log_buffer)[-pattern_length:] == self.current_pattern[start_index:]

    def print_pattern(self):
        if self.pattern_count > 1:
            self.print_log(f"The following pattern repeated {self.pattern_count} times:")
            for msg in self.current_pattern:
                self.print_log(f"  {msg}")
        elif self.pattern_count == 1:
            for msg in self.current_pattern:
                self.print_log(msg)
        self.pattern_count = 0

    def print_log(self, msg):
        self.context.Log(msg)

    def error(self, msg):
        self.Log(msg, trsh=0)

    def warning(self, msg):
        self.Log(msg, trsh=1)

    def info(self, msg):
        self.Log(msg, trsh=2)

    def debug(self, msg):
        self.Log(msg, trsh=3)

    def trace(self, msg):
        self.Log(msg, trsh=4)

    def dataframe(self, data):
        if isinstance(data, list):
            columns = list(data[0].keys())
        else:
            columns = list(data.keys())

        df = pd.DataFrame(data, columns=columns)

        if df.shape[0] > 0:
            self.info(f"\n{df.to_string(index=False)}")

    def __del__(self):
        self.print_pattern()

