# region imports
from AlgorithmImports import *
# endregion

class Base:

    """
    Base class for processing option contracts. 
    Contains a set of parameters and a method to evaluate contracts.
    
    Attributes:
        parameters (dict): Dictionary containing evaluation parameters.
    """
    
    def __init__(self):
        # Initialize with base parameters
        pass
    
    def evaluate_spreads(self, contracts, wingSizes):
        """
        Evaluate an array of option contracts and return parameters 
        to be sent to the order package.
        
        Args:
            contracts (list): List of option contracts to evaluate.
        
        Returns:
            dict: Parameters to be passed back to the order package.
        """
        best_spread = []
   
        return best_spread