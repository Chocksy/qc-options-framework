# region imports
from AlgorithmImports import *
# endregion

from Tools import Logger, ContractUtils, BSM

class OrderBuilder:
    """
    Manages the creation and retrieval of option contracts based on specified criteria to facilitate order construction.
    This includes selecting contracts by type, proximity to the money, delta values, and creating spreads and straddles.

    Attributes:
        context (Any): Contextual information and settings from the QCAlgorithm.
        bsm (BSM): An instance of a Black-Scholes-Merton pricing model for options valuation.
        logger (Logger): Logger for capturing and reporting runtime information.
        contractUtils (ContractUtils): Utility class for handling operations related to contracts.
    """
    #TODO
    #  \param[in] context is a reference to the QCAlgorithm instance. The following attributes are used from the context:
    #    - slippage: (Optional) controls how the mid-price of an order is adjusted to include slippage.
    #    - targetPremium: (Optional) used to determine how many contracts to buy/sell.
    #    - maxOrderQuantity: (Optional) Caps the number of contracts that are bought/sold (Default: 1).
    #         If targetPremium == None  -> This is the number of contracts bought/sold.
    #         If targetPremium != None  -> The order is executed only if the number of contracts required
    #           to reach the target credit/debit does not exceed the maxOrderQuantity
   
    def __init__(self, context):
        self.context = context # Set the context (QCAlgorithm object)
        self.bsm = BSM(context) # Initialize the BSM pricing model
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel) # Set the logger
        self.contractUtils = ContractUtils(context) # Initialize the contract utils

    def optionTypeFilter(self, contract, type = None):
        """
        Filters contracts by option type (Call or Put).

        Args:
            contract (OptionContract): The contract to check.
            type (str, optional): The type of option to filter ('call', 'put', None for any type).

        Returns:
            bool: True if the contract matches the type, False otherwise.
        """
        if type is None:
            return True

        type = type.lower()
        if type == "put":
            return contract.Right == OptionRight.Put
        elif type == "call":
            return contract.Right == OptionRight.Call
        else:
            return True

    def getATM(self, contracts, type = None):
        """
        Retrieves At-The-Money (ATM) contracts based on the underlying asset's current price.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            type (str, optional): Filters the contracts by type ('call', 'put', or 'both').

        Returns:
            list[OptionContract]: List of ATM option contracts.
        """
        # Initialize result
        atm_contracts = []

        # Sort the contracts based on how close they are to the current price of the underlying.
        # Filter them by the selected contract type (Put/Call or both)
        sorted_contracts = sorted([contract
                                        for contract in contracts
                                        if self.optionTypeFilter(contract, type)
                                    ]
                                    , key = lambda x: abs(x.Strike - self.contractUtils.getUnderlyingLastPrice(x))
                                    , reverse = False
                                    )

        # Check if any contracts were returned after the filtering
        if len(sorted_contracts) > 0:
            if type == None or type.lower() == "both":
                # Select the first two contracts (one Put and one Call)
                Ncontracts = min(len(sorted_contracts), 2)
            else:
                # Select the first contract (either Put or Call, based on the type specified)
                Ncontracts = 1
            # Extract the selected contracts
            atm_contracts = sorted_contracts[0:Ncontracts]
        # Return result
        return atm_contracts

    def getATMStrike(self, contracts):
        """
        Retrieves the strike price of the ATM contract.

        Args:
            contracts (list[OptionContract]): List of option contracts.

        Returns:
            float: The strike price of the ATM contract, or None if no ATM contract is found.
        """
        ATMStrike = None
        # Get the ATM contracts
        atm_contracts = self.getATM(contracts)
        # Check if any contracts were found
        if len(atm_contracts) > 0:
            # Get the Strike of the first contract
            ATMStrike = atm_contracts[0].Strike
        # Return result
        return ATMStrike

    def getDeltaContract(self, contracts, delta = None):
        """
        Retrieves the contract closest to a specified delta value.

        Args:
            contracts (list[OptionContract]): Sorted list of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            OptionContract: The contract closest to the specified delta, or None if not found.
        """
        # Skip processing if the option type or Delta has not been specified
        if delta == None or not contracts:
            return

        leftIdx = 0
        rightIdx = len(contracts)-1

        # Compute the Greeks for the contracts at the extremes
        self.bsm.setGreeks([contracts[leftIdx], contracts[rightIdx]])

        # Check if the requested Delta is outside of the range
        if contracts[rightIdx].Right == OptionRight.Call:
            # Check if the furthest OTM Call has a Delta higher than the requested Delta
            if abs(contracts[rightIdx].BSMGreeks.Delta) > delta/100.0:
                # The requested delta is outside the boundary, return the strike of the furthest OTM Call
                return contracts[rightIdx]
            # Check if the furthest ITM Call has a Delta lower than the requested Delta
            elif abs(contracts[leftIdx].BSMGreeks.Delta) < delta/100.0:
                # The requested delta is outside the boundary, return the strike of the furthest ITM Call
                return contracts[leftIdx]
        else:
            # Check if the furthest OTM Put has a Delta higher than the requested Delta
            if abs(contracts[leftIdx].BSMGreeks.Delta) > delta/100.0:
                # The requested delta is outside the boundary, return the strike of the furthest OTM Put
                return contracts[leftIdx]
            # Check if the furthest ITM Put has a Delta lower than the requested Delta
            elif abs(contracts[rightIdx].BSMGreeks.Delta) < delta/100.0:
                # The requested delta is outside the boundary, return the strike of the furthest ITM Put
                return contracts[rightIdx]

        # The requested Delta is inside the range, use the Bisection method to find the contract with the closest Delta
        while (rightIdx-leftIdx) > 1:
            # Get the middle point
            middleIdx = round((leftIdx + rightIdx)/2.0)
            middleContract = contracts[middleIdx]
            # Compute the greeks for the contract in the middle
            self.bsm.setGreeks(middleContract)
            contractDelta = contracts[middleIdx].BSMGreeks.Delta
            # Determine which side we need to continue the search
            if(abs(contractDelta) > delta/100.0):
                if middleContract.Right == OptionRight.Call:
                    # The requested Call Delta is on the right side
                    leftIdx = middleIdx
                else:
                    # The requested Put Delta is on the left side
                    rightIdx = middleIdx
            else:
                if middleContract.Right == OptionRight.Call:
                    # The requested Call Delta is on the left side
                    rightIdx = middleIdx
                else:
                    # The requested Put Delta is on the right side
                    leftIdx = middleIdx

        # At this point where should only be two contracts remaining: choose the contract with the closest Delta
        deltaContract = sorted([contracts[leftIdx], contracts[rightIdx]]
                                , key = lambda x: abs(abs(x.BSMGreeks.Delta) - delta/100.0)
                                , reverse = False
                                )[0]

        return deltaContract

    def getDeltaStrike(self, contracts, delta = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        deltaStrike = None
        # Get the contract with the closest Delta
        deltaContract = self.getDeltaContract(contracts, delta = delta)
        # Check if we got any contract
        if deltaContract != None:
            # Get the strike
            deltaStrike = deltaContract.Strike
        # Return the strike
        return deltaStrike


    def getFromDeltaStrike(self, contracts, delta = None, default = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        fromDeltaStrike = default
        # Get the call with the closest Delta
        deltaContract = self.getDeltaContract(contracts, delta = delta)
        # Check if we found the contract
        if deltaContract:
            if abs(deltaContract.BSMGreeks.Delta) >= delta/100.0:
                # The contract is in the required range. Get the Strike
                fromDeltaStrike = deltaContract.Strike
            else:
                # Calculate the offset: +0.01 in case of Puts, -0.01 in case of Calls
                offset = 0.01 * (2*int(deltaContract.Right == OptionRight.Put)-1)
                # The contract is outside of the required range. Get the Strike and add (Put) or subtract (Call) a small offset so we can filter for contracts above/below this strike
                fromDeltaStrike = deltaContract.Strike + offset
        return fromDeltaStrike

    def getToDeltaStrike(self, contracts, delta = None, default = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        toDeltaStrike = default
        # Get the put with the closest Delta
        deltaContract = self.getDeltaContract(contracts, delta = delta)
        # Check if we found the contract
        if deltaContract:
            if abs(deltaContract.BSMGreeks.Delta) <= delta/100.0:
                # The contract is in the required range. Get the Strike
                toDeltaStrike = deltaContract.Strike
            else:
                # Calculate the offset: +0.01 in case of Calls, -0.01 in case of Puts
                offset = 0.01 * (2*int(deltaContract.Right == OptionRight.Call)-1)
                # The contract is outside of the required range. Get the Strike and add (Call) or subtract (Put) a small offset so we can filter for contracts above/below this strike
                toDeltaStrike = deltaContract.Strike + offset
        return toDeltaStrike

    def getPutFromDeltaStrike(self, contracts, delta = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        return self.getFromDeltaStrike(contracts, delta = delta, default = 0.0)

    def getCallFromDeltaStrike(self, contracts, delta = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        return self.getFromDeltaStrike(contracts, delta = delta, default = float('Inf'))

    def getPutToDeltaStrike(self, contracts, delta = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        return self.getToDeltaStrike(contracts, delta = delta, default = float('Inf'))

    def getCallToDeltaStrike(self, contracts, delta = None):
        """
        Retrieves the strike price of the contract with the closest delta value.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            delta (float, optional): The target delta value.

        Returns:
            float: The strike price of the contract with the closest delta, or None if not found.
        """
        return self.getToDeltaStrike(contracts, delta = delta, default = 0)

    def getContracts(self, contracts, type = None, fromDelta = None, toDelta = None, fromStrike = None, toStrike = None, fromPrice = None, toPrice = None, reverse = False):
        """
        Filters and sorts option contracts based on specified criteria.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            type (str, optional): The type of option to filter ('call', 'put', or 'both').
            fromDelta (float, optional): The minimum delta value.
            toDelta (float, optional): The maximum delta value.
            fromStrike (float, optional): The minimum strike price.
            toStrike (float, optional): The maximum strike price.
            fromPrice (float, optional): The minimum option price.
            toPrice (float, optional): The maximum option price.
            reverse (bool, optional): If True, sort the contracts in descending order.

        Returns:
            list[OptionContract]: Filtered and sorted list of option contracts.
        """
        # Make sure all constraints are set
        fromStrike = fromStrike or 0
        fromPrice = fromPrice or 0
        toStrike = toStrike or float('inf')
        toPrice = toPrice or float('inf')

        # Get the Put contracts, sorted by ascending strike. Apply the Strike/Price constraints
        puts = []
        if type == None or type.lower() == "put":
            puts = sorted([contract
                            for contract in contracts
                                if self.optionTypeFilter(contract, "Put")
                                # Strike constraint
                                and (fromStrike <= contract.Strike <= toStrike)
                                # The option contract is tradable
                                and self.contractUtils.getSecurity(contract).IsTradable
                                # Option price constraint (based on the mid-price)
                                and (fromPrice <= self.contractUtils.midPrice(contract) <= toPrice)
                        ]
                        , key = lambda x: x.Strike
                        , reverse = False
                        )

        # Get the Call contracts, sorted by ascending strike. Apply the Strike/Price constraints
        calls = []
        if type == None or type.lower() == "call":
            calls = sorted([contract
                            for contract in contracts
                                if self.optionTypeFilter(contract, "Call")
                                # Strike constraint
                                and (fromStrike <= contract.Strike <= toStrike)
                                # The option contract is tradable
                                and self.contractUtils.getSecurity(contract).IsTradable
                                # Option price constraint (based on the mid-price)
                                and (fromPrice <= self.contractUtils.midPrice(contract) <= toPrice)
                            ]
                            , key = lambda x: x.Strike
                            , reverse = False
                            )


        deltaFilteredPuts = puts
        deltaFilteredCalls = calls
        # Check if we need to filter by Delta
        if (fromDelta or toDelta):
            # Find the strike range for the Puts based on the From/To Delta
            putFromDeltaStrike = self.getPutFromDeltaStrike(puts, delta = fromDelta)
            putToDeltaStrike = self.getPutToDeltaStrike(puts, delta = toDelta)
            # Filter the Puts based on the delta-strike range
            deltaFilteredPuts = [contract for contract in puts
                                    if putFromDeltaStrike <= contract.Strike <= putToDeltaStrike
                                ]

            # Find the strike range for the Calls based on the From/To Delta
            callFromDeltaStrike = self.getCallFromDeltaStrike(calls, delta = fromDelta)
            callToDeltaStrike = self.getCallToDeltaStrike(calls, delta = toDelta)
            # Filter the Puts based on the delta-strike range. For the calls, the Delta decreases with increasing strike, so the order of the filter is inverted
            deltaFilteredCalls = [contract for contract in calls
                                    if callToDeltaStrike <= contract.Strike <= callFromDeltaStrike
                                ]


        # Combine the lists and Sort the contracts by their strike in the specified order.
        result = sorted(deltaFilteredPuts + deltaFilteredCalls
                        , key = lambda x: x.Strike
                        , reverse = reverse
                        )
        # Return result
        return result

    def getPuts(self, contracts, fromDelta = None, toDelta = None, fromStrike = None, toStrike = None, fromPrice = None, toPrice = None):
        """
        Retrieves Put option contracts based on specified criteria.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            fromDelta (float, optional): The minimum delta value.
            toDelta (float, optional): The maximum delta value.
            fromStrike (float, optional): The minimum strike price.
            toStrike (float, optional): The maximum strike price.
            fromPrice (float, optional): The minimum option price.
            toPrice (float, optional): The maximum option price.

        Returns:
            list[OptionContract]: Filtered and sorted list of Put option contracts.
        """
        # Sort the Put contracts by their strike in reverse order. Filter them by the specified criteria (Delta/Strike/Price constrains)
        return self.getContracts(contracts
                                , type = "Put"
                                , fromDelta = fromDelta
                                , toDelta = toDelta
                                , fromStrike = fromStrike
                                , toStrike = toStrike
                                , fromPrice = fromPrice
                                , toPrice = toPrice
                                , reverse = True
                                )

    def getCalls(self, contracts, fromDelta = None, toDelta = None, fromStrike = None, toStrike = None, fromPrice = None, toPrice = None):
        """
        Retrieves Call option contracts based on specified criteria.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            fromDelta (float, optional): The minimum delta value.
            toDelta (float, optional): The maximum delta value.
            fromStrike (float, optional): The minimum strike price.
            toStrike (float, optional): The maximum strike price.
            fromPrice (float, optional): The minimum option price.
            toPrice (float, optional): The maximum option price.

        Returns:
            list[OptionContract]: Filtered and sorted list of Call option contracts.
        """
        # Sort the Call contracts by their strike in ascending order. Filter them by the specified criteria (Delta/Strike/Price constrains)
        return self.getContracts(contracts
                                , type = "Call"
                                , fromDelta = fromDelta
                                , toDelta = toDelta
                                , fromStrike = fromStrike
                                , toStrike = toStrike
                                , fromPrice = fromPrice
                                , toPrice = toPrice
                                , reverse = False
                                )

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

    def getSpread(self, contracts, type, strike = None, delta = None, wingSize = None, sortByStrike = False, fromPrice = None, toPrice = None, premiumOrder = 'max'):
        """
        Retrieves the best spread contract based on specified criteria.

        Args:
            contracts (list[OptionContract]): List of option contracts.
            type (str): The type of option to filter ('call', 'put', or 'both').
            strike (float, optional): The target strike price.
            delta (float, optional): The target delta value.
            wingSize (float, optional): The distance from the ATM strike.
            sortByStrike (bool, optional): If True, sort the contracts by strike.
            fromPrice (float, optional): The minimum option price.
            toPrice (float, optional): The maximum option price.
            premiumOrder (str, optional): The order of the premium ('max' or 'min').

        Returns:
            list[OptionContract]: The best spread contract, or None if not found.
        """
        # Type is a required parameter
        if type == None:
            self.logger.error(f"Input parameter type = {type} is invalid. Valid values: 'Put'|'Call'")
            return

        type = type.lower()
        if type == "put":
            # Get all Puts with a strike lower than the given strike and delta lower than the given delta
            sorted_contracts = self.getPuts(contracts, toDelta = delta, toStrike = strike)
        elif type == "call":
            # Get all Calls with a strike higher than the given strike and delta lower than the given delta
            sorted_contracts = self.getCalls(contracts, toDelta = delta, fromStrike = strike)
        else:
            self.logger.error(f"Input parameter type = {type} is invalid. Valid values: 'Put'|'Call'")
            return

        # Initialize the result and the best premium
        best_spread = []
        best_premium = -float('inf') if premiumOrder == 'max' else float('inf')
        self.logger.debug(f"wingSize: {wingSize}, premiumOrder: {premiumOrder}, fromPrice: {fromPrice}, toPrice: {toPrice}, sortByStrike: {sortByStrike}, strike: {strike}")
        if strike is not None:
            wing = self.getWing(sorted_contracts, wingSize = wingSize)
            self.logger.debug(f"STRIKE: wing: {wing}")
            # Check if we have any contracts
            if(len(sorted_contracts) > 0):
                # Add the first leg
                best_spread.append(sorted_contracts[0])
                if wing != None:
                    # Add the wing
                    best_spread.append(wing)
        else:
            # Iterate over sorted contracts
            for i in range(len(sorted_contracts) - 1):
                # Get the wing
                wing = self.getWing(sorted_contracts[i:], wingSize = wingSize)
                self.logger.debug(f"NO STRIKE: wing: {wing}")
                if wing is not None:
                    # Calculate the net premium
                    net_premium = abs(self.contractUtils.midPrice(sorted_contracts[i]) - self.contractUtils.midPrice(wing))
                    self.logger.debug(f"fromPrice: {fromPrice} <= net_premium: {net_premium} <= toPrice: {toPrice}")
                    # Check if the net premium is within the specified price range
                    if fromPrice <= net_premium <= toPrice:
                        # Check if this spread has a better premium
                        if (premiumOrder == 'max' and net_premium > best_premium) or (premiumOrder == 'min' and net_premium < best_premium):
                            best_spread = [sorted_contracts[i], wing]
                            best_premium = net_premium

        # By default, the legs of a spread are sorted based on their distance from the ATM strike.
        # - For Call spreads, they are already sorted by increasing strike
        # - For Put spreads, they are sorted by decreasing strike
        # In some cases it might be more convenient to return the legs ordered by their strike (i.e. in case of Iron Condors/Flys)
        if sortByStrike:
            best_spread = sorted(best_spread, key = lambda x: x.Strike, reverse = False)

        return best_spread

    def getPutSpread(self, contracts, strike = None, delta = None, wingSize = None, sortByStrike = False):
        """
        Retrieve a Put spread of option contracts based on specified criteria.

        Args:
            contracts: A list of option contracts to use for creating the Put spread.
            strike: (Optional) Specific strike price to filter Put contracts.
            delta: (Optional) Delta value to filter Put contracts.
            wingSize: (Optional) Distance from the first leg to the wing contract.
            sortByStrike: (Optional) If True, sort the spread legs by their strike price; otherwise, keep default sorting.

        Returns:
            List: A list of option contracts representing the Put spread, sorted based on specified criteria.
        """
        return self.getSpread(contracts, "Put", strike = strike, delta = delta, wingSize = wingSize, sortByStrike = sortByStrike)

    def getCallSpread(self, contracts, strike = None, delta = None, wingSize = None, sortByStrike = True):
        """
        Retrieve a Call spread of option contracts based on specified criteria.

        Args:
            contracts: A list of option contracts to use for creating the Call spread.
            strike: (Optional) Specific strike price to filter Call contracts.
            delta: (Optional) Delta value to filter Call contracts.
            wingSize: (Optional) Distance from the first leg to the wing contract.
            sortByStrike: (Optional) If True, sort the spread legs by their strike price; otherwise, keep default sorting.

        Returns:
            List: A list of option contracts representing the Call spread, sorted based on specified criteria.
        """
        return self.getSpread(contracts, "Call", strike = strike, delta = delta, wingSize = wingSize, sortByStrike = sortByStrike)

