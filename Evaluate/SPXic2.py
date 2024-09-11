# region imports
from AlgorithmImports import *
from Tools import Logger, ContractUtils, BSM

# endregion

# Your New Python File

# Child class: AdvancedOptionProcessor
class SPXic2:
    """
    Child class that extends the base contract evaluation functionality.
    Adds additional parameters and custom logic for evaluating contracts.
    
    Attributes:
        parameters (dict): Merged dictionary of base and additional parameters.
    """
    
    DEFAULT_PARAMETERS = {
        # Target risk level in dollars for each order
        "target_risk": 10000,
        "min_delta": -0.10,
        "max_delta": -0.04,
        "min_dte": 2,
        "min_strike": 1200,
        "fromPrice": 0.1,
        "toPrice": 0.4,
    }
    
    def __init__(self,context, strategy):
        super().__init__()
        # Merge base and extra parameters
        self.parameters = self.DEFAULT_PARAMETERS
        self.context = context
        self.bsm = BSM(context) # Initialize the BSM pricing model
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel) # Set the logger
        self.contractUtils = ContractUtils(context) # Initialize the contract utils
        self.strategy = strategy
        
    def evaluate_spreads(self, contracts, wingSizes, fromPrice = None, toPrice = None, sortByStrike = False):
        # Initialize the result and the best premium - examples
        best_spread = []
        # Get algorithm default parameters 
        target_risk = self.parameters["target_risk"]
        min_delta = self.parameters["min_delta"]
        max_delta = self.parameters["max_delta"]
        min_strike = self.parameters["min_strike"]
        fromPrice = fromPrice if fromPrice else self.parameters["fromPrice"] 
        toPrice= toPrice if toPrice else self.parameters["toPrice"]

        # read the array of winSizes or one integer value from the strategy
        wingSizes = wingSizes if isinstance(wingSizes, list) else [wingSizes]

        for wingSize in wingSizes:
            # Iterate over sorted contracts
            for i in range(len(contracts) - 1):
                # Get the wing
                wing = self.getWing(contracts[i:], wingSize = wingSize)
                self.logger.debug(f"NO STRIKE: wing: {wing}")
                if wing is not None:
                    # calculate_spread_metrics
                    if fromPrice <= net_premium <= toPrice:
                        # Calculate the net premium
                        net_premium = abs(self.contractUtils.midPrice(contracts[i]) - self.contractUtils.midPrice(wing))                
                        if fromPrice <= net_premium <= toPrice:   
                            best_spread = [contracts[i], wing]
        if sortByStrike:
            best_spread = sorted(best_spread, key = lambda x: x.Strike, reverse = False)        

        # return best_spread
        return best_spread

    def getWing(self, contracts, wingSize = None):
        """
        Retrieves the wing contract at the requested distance.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            wingSize (float, optional): The distance from the ATM strike.

        Returns:
            OptionContract: The wing contract, or None if not found.
        """
        # Make sure the wingSize is specified
        wingSize = wingSize or 0

        # Initialize output
        wingContract = None

        if len(contracts) > 1 and wingSize > 0:
            # Get the short strike
            firstLegStrike = contracts[0].Strike
            # keep track of the wing size based on the long contract being selected
            currentWings = 0
            # Loop through all contracts
            for contract in contracts[1:]:
                # Select the long contract as long as it is within the specified wing size
                if abs(contract.Strike - firstLegStrike) <= wingSize:
                    currentWings = abs(contract.Strike - firstLegStrike)
                    wingContract = contract
                else:
                    # We have exceeded the wing size, check if the distance to the requested wing size is closer than the contract previously selected
                    if (abs(contract.Strike - firstLegStrike) - wingSize < wingSize - currentWings):
                        wingContract = contract
                    break
            ### Loop through all contracts
        ### if wingSize > 0

        return wingContract
