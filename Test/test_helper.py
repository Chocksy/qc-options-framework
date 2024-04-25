#region imports
from AlgorithmImports import *
#endregion
# Import necessary modules and classes
import os
import sys
import pytest
import unittest
from unittest.mock import MagicMock

def add_project_root_to_sys_path():
    """Adds the project root directory to sys.path."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(project_root)

add_project_root_to_sys_path()
