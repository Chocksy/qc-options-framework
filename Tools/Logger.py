#region imports
from AlgorithmImports import *
#endregion
import sys
import pandas as pd
from collections import deque, defaultdict, OrderedDict
from datetime import datetime, timedelta
import hashlib
import json

class LogMessage:
    def __init__(self, level, class_name, function_name, message, timestamp):
        self.level = level
        self.class_name = class_name
        self.function_name = function_name
        self.message = message
        self.timestamp = timestamp
        self._hash = None
        self._base_hash = None

    @property
    def hash(self):
        if self._hash is None:
            content = f"{self.level}|{self.class_name}|{self.function_name}|{self.message}"
            self._hash = hashlib.md5(content.encode()).hexdigest()
        return self._hash

    @property
    def base_hash(self):
        if self._base_hash is None:
            import re
            try:
                # Standardize the message by:
                # 1. Replacing all numeric values with "NUM"
                # 2. Normalizing whitespace
                # 3. Converting to lowercase for case-insensitive matching
                # 4. Removing any special characters that might vary
                
                # First replace all numbers with NUM
                template = re.sub(r'[-+]?[0-9,]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', 'NUM', self.message)
                
                # Normalize whitespace (multiple spaces to single space)
                template = re.sub(r'\s+', ' ', template)
                
                # Convert to lowercase
                template = template.lower()
                
                # Remove some common variable characters
                template = re.sub(r'[:\[\]{}()]', '', template)
                
                # Create a content string with essential parts
                content = f"{self.level.lower()}|{self.class_name.lower()}|{self.function_name.lower()}|{template}"
                
                # Hash the standardized content
                self._base_hash = hashlib.md5(content.encode()).hexdigest()
            except Exception:
                # Fallback to a simpler hash if there's an error
                content = f"{self.level}|{self.class_name}|{self.function_name}"
                self._base_hash = hashlib.md5(content.encode()).hexdigest()
        return self._base_hash

    def extract_value(self):
        """Extract the numeric value from a message, assuming it's the last number"""
        import re
        try:
            # Enhanced pattern to catch more numeric formats
            # This pattern catches: integers, floats, scientific notation, and numbers with commas
            pattern = r'[-+]?[0-9,]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?'
            numbers = re.findall(pattern, self.message)
            
            # Clean up any numbers with commas
            cleaned_numbers = []
            for num in numbers:
                if ',' in num:
                    num = num.replace(',', '')
                cleaned_numbers.append(num)
                
            # Try to return the last number if any were found
            return float(cleaned_numbers[-1]) if cleaned_numbers else None
        except Exception:
            # If any error occurs during extraction, log it and return None
            return None

class MessageGroup:
    def __init__(self, first_message):
        self.base_hash = first_message.base_hash
        self.messages = [first_message]
        self.first_time = first_message.timestamp
        self.last_time = first_message.timestamp
        self.level = first_message.level
        self.class_name = first_message.class_name
        self.function_name = first_message.function_name
        self.base_message = first_message.message

    def add_message(self, message):
        if message.base_hash != self.base_hash:
            return False
        self.messages.append(message)
        self.last_time = message.timestamp
        return True

    def _analyze_values(self):
        """Analyze numeric values in the message group"""
        values = []
        timestamps = []
        for msg in sorted(self.messages, key=lambda x: x.timestamp):
            value = msg.extract_value()
            if value is not None:
                values.append(value)
                timestamps.append(msg.timestamp)
        return values, timestamps

    def _get_trend_analysis(self, values, timestamps):
        """Generate trend analysis for the values"""
        if not values or len(values) < 2:
            return ""

        # Find key changes (significant peaks and valleys)
        key_changes = []
        for i in range(1, len(values)-1):
            # Look for local maxima and minima
            if (values[i] > values[i-1] and values[i] > values[i+1]) or \
               (values[i] < values[i-1] and values[i] < values[i+1]):
                key_changes.append((timestamps[i], values[i]))

        # Limit to most significant changes
        if len(key_changes) > 4:
            # Sort by absolute change magnitude
            key_changes.sort(key=lambda x: abs(x[1] - values[0]), reverse=True)
            key_changes = key_changes[:4]
            # Resort by time
            key_changes.sort(key=lambda x: x[0])

        if not key_changes:
            return ""

        # Format changes
        changes = [f"{'↑' if x[1] > values[0] else '↓'}{x[1]:.2f}({x[0].strftime('%H:%M')})" for x in key_changes]
        return " " + " ".join(changes)

    def _get_distribution_analysis(self, values):
        """Generate distribution analysis for the values"""
        if not values or len(values) < 3:
            return ""

        # Create bins for the distribution
        min_val = min(values)
        max_val = max(values)
        
        # If all values are the same, return a special format
        if min_val == max_val:
            return f"Distribution: [constant={min_val:.2f}]"
            
        bin_size = (max_val - min_val) / 3
        bins = defaultdict(int)
        
        for v in values:
            bin_idx = int((v - min_val) / bin_size)
            if bin_idx == 3:  # Handle edge case for max value
                bin_idx = 2
            bins[bin_idx] += 1

        # Format distribution
        dist_parts = ["Distribution:"]
        for i in range(3):
            if bins[i] > 0:
                bin_start = min_val + i * bin_size
                bin_end = min_val + (i + 1) * bin_size
                dist_parts.append(f"[{bin_start:.1f}-{bin_end:.1f}: {bins[i]}]")

        return " ".join(dist_parts)

    def get_summary(self):
        """Generate an enhanced summary of the messages with clear visual formatting"""
        if len(self.messages) == 1:
            return self._format_message(self.messages[0])

        values, timestamps = self._analyze_values()
        if not values:
            return self._format_message(self.messages[0])

        # Basic statistics
        mean_val = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)
        
        # Format time range
        time_range = f"{self.first_time.strftime('%H:%M:%S')}-{self.last_time.strftime('%H:%M:%S')}"
        
        # Build the summary message with clear sections
        sections = []
        
        # Base message
        base = f"{time_range} {self.level} -> {self.class_name}{self.function_name}: {self.base_message}"
        sections.append(base)
        
        # Statistics section
        stats = f"    Stats: mean={mean_val:.2f}, min={min_val:.2f}, max={max_val:.2f}"
        sections.append(stats)
        
        # Trend analysis
        trend = self._get_trend_analysis(values, timestamps)
        if trend:
            sections.append(f"    Trend:{trend}")
        
        # Distribution
        dist = self._get_distribution_analysis(values)
        if dist:
            sections.append(f"    {dist}")
        
        # Sample count
        sections.append(f"    Samples: {len(values)}")
        
        # Combine all sections with newlines
        return "\n".join(sections)

    def _format_message(self, msg):
        return (f"{msg.timestamp.strftime('%H:%M:%S')} {msg.level} -> "
                f"{msg.class_name}{msg.function_name}: {msg.message}")

class Logger:
    def __init__(self, context, className=None, logLevel=0):
        self.context = context
        self.className = className
        self.logLevel = logLevel
        
        if not hasattr(self.context, 'logger_storage'):
            self.context.logger_storage = {
                'daily_messages': defaultdict(list),  # hash -> list of messages
                'message_groups': defaultdict(list),  # base_hash -> MessageGroup
            }

        # Add logger_context for shared state across logger instances
        if not hasattr(self.context, 'logger_context'):
            self.context.logger_context = {
                'last_summary_day': None
            }

    def Log(self, msg, trsh=0):
        if trsh > self.logLevel:
            return
        
        # Check if message is a string, if not convert with a warning
        if not isinstance(msg, str):
            msg = f"PLEASE USE string messages: {str(msg)}"
            
        log_msg = LogMessage(
            level=["ERROR", "WARNING", "INFO", "DEBUG", "TRACE"][min(trsh, 4)],
            class_name=f"{self.className}." if self.className else "",
            function_name=sys._getframe(2).f_code.co_name,
            message=msg,
            timestamp=self.context.Time
        )
        
        if self.context.LiveMode:
            self._log_immediate(log_msg)
            return

        # Store message in the appropriate collection
        try:
            # First try to extract a numeric value
            numeric_value = log_msg.extract_value()
            
            if numeric_value is not None:
                # If we got a numeric value, try to add to an existing group or create a new one
                groups = self.context.logger_storage['message_groups']
                if log_msg.base_hash not in groups:
                    # Create a new message group
                    groups[log_msg.base_hash] = MessageGroup(log_msg)
                else:
                    # Add to existing message group
                    added = groups[log_msg.base_hash].add_message(log_msg)
                    if not added:
                        # If adding to group failed, treat as a regular message
                        daily_messages = self.context.logger_storage['daily_messages']
                        daily_messages[log_msg.hash].append(log_msg)
            else:
                # No numeric value, store as a regular message
                daily_messages = self.context.logger_storage['daily_messages']
                daily_messages[log_msg.hash].append(log_msg)
        except Exception:
            # Safety fallback - if anything goes wrong, store as a regular message
            try:
                daily_messages = self.context.logger_storage['daily_messages']
                daily_messages[log_msg.hash].append(log_msg)
            except:
                # Last resort - log immediately if even storing fails
                self._log_immediate(log_msg)

    def process_and_output_daily_logs(self):
        if self.context.LiveMode:
            self.context.logger_storage['daily_messages'].clear()
            self.context.logger_storage['message_groups'].clear()
            return
            
        daily_messages = self.context.logger_storage['daily_messages']
        message_groups = self.context.logger_storage['message_groups']
        
        if not daily_messages and not message_groups:
            return

        # Use context's current time for the day
        current_day = self.context.Time.date()
            
        # Only process if we haven't already processed this day
        # Use the shared context value instead of instance variable
        if current_day == self.context.logger_context['last_summary_day']:
            return
            
        # Update the shared context value
        self.context.logger_context['last_summary_day'] = current_day
        
        self.context.Log("---------------------------------")
        self.context.Log(f"Daily Log Summary - {current_day}")
        self.context.Log("---------------------------------")
        
        # Process regular messages
        for messages in daily_messages.values():
            first_msg = messages[0]
            count = len(messages)
            if count > 1:
                self.context.Log(f"{first_msg.timestamp.strftime('%H:%M:%S')} {first_msg.level} -> "
                               f"{first_msg.class_name}{first_msg.function_name}: {first_msg.message} "
                               f"(repeated {count} times)")
            else:
                self._log_immediate(first_msg)
        
        # Process grouped messages
        for group in message_groups.values():
            self.context.Log(group.get_summary())
        
        self.context.Log("")
        
        # Clear the storage only for messages from this day or earlier
        for hash_key in list(daily_messages.keys()):
            if daily_messages[hash_key][0].timestamp.date() <= current_day:
                daily_messages.pop(hash_key)
                
        for base_hash in list(message_groups.keys()):
            if message_groups[base_hash].first_time.date() <= current_day:
                message_groups.pop(base_hash)

    def _log_immediate(self, log_msg):
        formatted_msg = (f"{log_msg.timestamp.strftime('%H:%M:%S')} {log_msg.level} -> "
                        f"{log_msg.class_name}{log_msg.function_name}: {log_msg.message}")
        self.context.Log(formatted_msg)

    def __del__(self):
        if hasattr(self, 'context') and hasattr(self.context, 'logger_storage'):
            self.process_and_output_daily_logs()

    # Convenience methods
    def error(self, msg): self.Log(msg, 0)
    def warning(self, msg): self.Log(msg, 1)
    def info(self, msg): self.Log(msg, 2)
    def debug(self, msg): self.Log(msg, 3)
    def trace(self, msg): self.Log(msg, 4)

    def dataframe(self, data):
        if isinstance(data, pd.DataFrame):
            self.Log(f"\n{data.to_string()}")
        else:
            self.Log(str(data))

    def summarize_dict(self, obj_dict):
        """
        Creates a summarized version of a dictionary of objects that have summarize methods.
        
        Args:
            obj_dict (dict): Dictionary of objects with summarize methods
            
        Returns:
            dict: Dictionary with the same keys but with summarized object values
        """
        if not obj_dict:
            return {}
            
        result = {}
        for k, v in obj_dict.items():
            if hasattr(v, 'summarize') and callable(getattr(v, 'summarize')):
                result[k] = v.summarize()
            else:
                result[k] = str(v)
                
        return result
