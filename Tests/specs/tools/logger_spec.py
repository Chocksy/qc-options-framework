from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, be_none
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
import hashlib
import re
from collections import defaultdict
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
import pandas as pd
from expects.matchers import Matcher
import sys

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Tools.Logger import Logger, LogMessage, MessageGroup

# Custom matchers
class BeEmpty(Matcher):
    def _match(self, subject):
        return len(subject) == 0, []

class BeAbove(Matcher):
    def __init__(self, expected):
        self._expected = expected

    def _match(self, subject):
        return subject > self._expected, []

be_empty = BeEmpty()
be_above = BeAbove

with description('Logger') as self:
    with before.each:
        self.context = MagicMock()
        self.context.Time = datetime.now()
        self.context.LiveMode = False  # Set to False for backtest mode
        self.context.Log = MagicMock()
        self.context.logger_storage = {
            'daily_messages': defaultdict(list),  # hash -> list of messages
            'message_groups': defaultdict(list),  # base_hash -> MessageGroup
        }
        self.logger = Logger(self.context, className="TestClass", logLevel=3)

    with context('LogMessage'):
        with it('initializes correctly'):
            msg = LogMessage("INFO", "TestClass", "test_func", "test message", datetime.now())
            expect(msg.level).to(equal("INFO"))
            expect(msg.class_name).to(equal("TestClass"))
            expect(msg.function_name).to(equal("test_func"))
            expect(msg.message).to(equal("test message"))

        with it('generates correct hash'):
            msg = LogMessage("INFO", "TestClass", "test_func", "test message", datetime.now())
            expected_content = "INFO|TestClass|test_func|test message"
            expected_hash = hashlib.md5(expected_content.encode()).hexdigest()
            expect(msg.hash).to(equal(expected_hash))

        with it('generates correct base_hash'):
            msg = LogMessage("INFO", "TestClass", "test_func", "Value is 123.45", datetime.now())
            base_hash = msg.base_hash
            expect(base_hash).not_to(be_none)
            msg2 = LogMessage("INFO", "TestClass", "test_func", "Value is 678.90", datetime.now())
            expect(msg2.base_hash).to(equal(base_hash))

        with context('extract_value'):
            with it('extracts numeric value from message'):
                msg = LogMessage("INFO", "TestClass", "test_func", "Value is 123.45", datetime.now())
                expect(msg.extract_value()).to(equal(123.45))
                
            with it('returns None when no numeric value'):
                msg = LogMessage("INFO", "TestClass", "test_func", "No numbers here", datetime.now())
                expect(msg.extract_value()).to(be_none)

    with context('MessageGroup'):
        with before.each:
            self.time = datetime.now()
            self.first_msg = LogMessage("INFO", "TestClass", "test_func", "Value is 100", self.time)
            self.group = MessageGroup(self.first_msg)

        with it('initializes correctly'):
            expect(self.group.base_hash).to(equal(self.first_msg.base_hash))
            expect(self.group.messages).to(contain(self.first_msg))
            expect(self.group.first_time).to(equal(self.time))
            expect(self.group.last_time).to(equal(self.time))

        with it('adds messages with matching base_hash'):
            new_msg = LogMessage("INFO", "TestClass", "test_func", "Value is 200", self.time + timedelta(minutes=1))
            result = self.group.add_message(new_msg)
            expect(result).to(be_true)
            expect(self.group.messages).to(contain(new_msg))

        with it('rejects messages with different base_hash'):
            diff_msg = LogMessage("INFO", "TestClass", "test_func", "Different message", self.time)
            result = self.group.add_message(diff_msg)
            expect(result).to(be_false)
            expect(self.group.messages).not_to(contain(diff_msg))

        with it('generates correct summary for single message'):
            summary = self.group.get_summary()
            expect(summary).to(contain(self.time.strftime('%H:%M:%S')))
            expect(summary).to(contain("Value is 100"))

        with it('generates correct summary for multiple messages'):
            new_msg = LogMessage("INFO", "TestClass", "test_func", "Value is 200", self.time + timedelta(minutes=1))
            self.group.add_message(new_msg)
            summary = self.group.get_summary()
            expect(summary).to(contain("Stats: mean=150.00"))
            expect(summary).to(contain("Samples: 2"))

    with context('Logger'):
        with it('groups numeric messages correctly'):
            self.context.LiveMode = False  # Ensure backtest mode
            self.logger.Log("Value is 100")
            expect(len(self.context.logger_storage['message_groups'])).to(equal(1))
            expect(len(self.context.logger_storage['message_groups'])).to(equal(1))

        with it('stores non-numeric messages correctly'):
            self.context.LiveMode = False  # Ensure backtest mode
            self.logger.Log("Regular message")
            expect(len(self.context.logger_storage['daily_messages'])).to(equal(1))

        with it('processes daily logs correctly'):
            self.context.LiveMode = False  # Ensure backtest mode
            self.logger.Log("Value is 100")
            self.logger.Log("Value is 200")
            self.logger.Log("Regular message")
            self.logger.process_and_output_daily_logs()
            expect(self.context.Log.call_count).to(be_above(3))

        with it('handles dataframe logging'):
            # Set LiveMode to True for immediate logging
            self.context.LiveMode = True
            df = pd.DataFrame({'A': [1, 2, 3]})
            self.logger.dataframe(df)
            expect(self.context.Log.call_count).to(equal(1))

            # Test non-dataframe input
            self.context.Log.reset_mock()
            self.logger.dataframe("not a dataframe")
            expect(self.context.Log.call_args[0][0]).to(contain("not a dataframe"))

    with context('log levels'):
        with it('handles different log levels'):
            # Set LiveMode to True for immediate logging
            self.context.LiveMode = True
            self.context.Log.reset_mock()
            
            with patch('sys._getframe') as mock_frame:
                frame = MagicMock()
                frame.f_code.co_name = "test_function"
                mock_frame.return_value = frame
                
                # Use self.logger instead of creating a new one
                self.logger.Log("error", 0)  # ERROR
                self.logger.Log("warning", 1)  # WARNING
                self.logger.Log("info", 2)  # INFO
                self.logger.Log("debug", 3)  # DEBUG
                self.logger.Log("trace", 4)  # TRACE
                
                expect(self.context.Log.call_count).to(equal(4))  # trace should be filtered out by logLevel=3

    with context('dataframe handling'):
        with it('handles dataframe logging'):
            context = MagicMock()
            context.Time = datetime.now()
            context.LiveMode = True
            logger = Logger(context, "TestClass")
            
            df = pd.DataFrame({'A': [1, 2, 3]})
            logger.dataframe(df)
            
            expect(context.Log.call_args[0][0]).to(contain(str(df)))
            
        with it('converts data to dataframe'):
            context = MagicMock()
            context.LiveMode = True
            logger = Logger(context, "TestClass")
            data = {'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']}
            result = logger.dataframe(data)
            expect(isinstance(result, pd.DataFrame)).to(be_true)
            expect(result.shape).to(equal((3, 2))) 