import sys
import numpy as np  # Import numpy once at the top level
from unittest.mock import patch
from .mocks.algorithm_imports import *

def patch_imports():
    """
    Creates a context for patching imports during tests
    Returns a tuple of context managers for use in with statements
    """
    # Store the original numpy in sys.modules to prevent reloading
    sys.modules['numpy'] = np
    
    mock_module = sys.modules[__name__]
    
    # Create the patch contexts
    patch_context1 = patch.dict('sys.modules', {
        'AlgorithmImports': mock_module,
        'numpy': np
    })
    
    # We need to patch the module in the Tools package
    patch_context2 = patch.dict('sys.modules', {
        'Tools.AlgorithmImports': mock_module
    })
    
    return patch_context1, patch_context2