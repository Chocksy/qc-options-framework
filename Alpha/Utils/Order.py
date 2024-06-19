#region imports
from AlgorithmImports import *
#endregion

import numpy as np
from .OrderBuilder import OrderBuilder
from Tools import ContractUtils, BSM, Logger
from Strategy import Position


class Order:
    def __init__(self, context, base):
        self.context = context
        self.base = base
        # Set the logger
        self.logger = Logger(context, className=type(self).__name__, logLevel=context.logLevel)
        # Initialize the BSM pricing model
        self.bsm = BSM(context)
        # Initialize the contract utils
        self.contractUtils = ContractUtils(context)
        # Initialize the Strategy Builder
        self.strategyBuilder = OrderBuilder(context)

    # Function to evaluate the P&L of the position
    def fValue(self, spotPrice, contracts, sides=None, atTime=None, openPremium=None):
        # Compute the theoretical value at the given Spot price and point in time
        prices = np.array(
            [
                self.bsm.bsmPrice(
                    contract,
                    sigma=contract.BSMImpliedVolatility,
                    spotPrice=spotPrice,
                    atTime=atTime,
                )
                for contract in contracts
            ]
        )
        # Total value of the position
        value = openPremium + sum(prices * np.array(sides))
        return value

    def getPayoff(self, spotPrice, contracts, sides):
        # Exit if there are no contracts to process
        if len(contracts) == 0:
            return 0

        # Initialize the counter
        n = 0
        # initialize the payoff
        payoff = 0
        for contract in contracts:
            # direction: Call -> +1, Put -> -1
            direction = 2*int(contract.Right == OptionRight.Call)-1
            # Add the payoff of the current contract
            payoff += sides[n] * max(0, direction * (spotPrice - contract.Strike))
            # Increment the counter
            n += 1

        # Return the payoff
        return payoff

    def computeOrderMaxLoss(self, contracts, sides):
        # Exit if there are no contracts to process
        if len(contracts) == 0:
            return 0

        # Get the current price of the underlying
        UnderlyingLastPrice = self.contractUtils.getUnderlyingLastPrice(contracts[0])
        # Evaluate the payoff at the extreme (spotPrice = 0)
        maxLoss = self.getPayoff(0, contracts, sides)
        # Evaluate the payoff at each strike
        for contract in contracts:
            maxLoss = min(maxLoss, self.getPayoff(contract.Strike, contracts, sides))

        # Evaluate the payoff at the extreme (spotPrice = 10x higher)
        maxLoss = min(maxLoss, self.getPayoff(UnderlyingLastPrice*10, contracts, sides))
        # Cap the payoff at zero: we are only interested in losses
        maxLoss = min(0, maxLoss)
        # Return the max loss
        return maxLoss

    def getMaxOrderQuantity(self):
        # Get the context
        context = self.context

        # Get the maximum order quantity parameter
        maxOrderQuantity = self.base.maxOrderQuantity
        # Get the targetPremiumPct
        targetPremiumPct = self.base.targetPremiumPct
        # Check if we are using dynamic premium targeting
        if targetPremiumPct != None:
            # Scale the maxOrderQuantity consistently with the portfolio growth
            maxOrderQuantity = round(maxOrderQuantity * (1 + context.Portfolio.TotalProfit / context.initialAccountValue))
            # Make sure we don't go below the initial parameter value
            maxOrderQuantity = max(self.base.maxOrderQuantity, maxOrderQuantity)
        # Return the result
        return maxOrderQuantity

    def isDuplicateOrder(self, contracts, sides):
        # Loop through all working orders of this strategy
        for orderTag in list(self.context.workingOrders):
            # Get the current working order
            workingOrder = self.context.workingOrders.get(orderTag)
            # Check if the number of contracts of this working order is the same as the number of contracts in the input list
            if workingOrder and workingOrder.insights == len(contracts):
                # Initialize the isDuplicate flag. Assume it's duplicate unless we find a mismatch
                isDuplicate = True
                # Loop through each pair (contract, side)
                for contract, side in zip(contracts, sides):
                    # Get the details of the contract
                    contractInfo = workingOrder.get(contract.Symbol)
                # If we cannot find this contract then it's not a duplicate
                if contractInfo == None:
                    isDuplicate = False
                    break
                # Get the orderSide and expiryStr properties
                orderSide = contractInfo.get("orderSide")
                expiryStr = contractInfo.get("expiryStr")
                # Check for a mismatch
                if (orderSide != side # Found the contract but it's on a different side (Sell/Buy)
                    or expiryStr != contract.Expiry.strftime("%Y-%m-%d") # Found the contract but it's on a different Expiry
                    ):
                    # It's not a duplicate. Brake this innermost loop
                    isDuplicate = False
                    break
                # Exit if we found a duplicate
                if isDuplicate:
                    return isDuplicate

        # If we got this far, there are no duplicates
        return False

    def limitOrderPrice(self, sides, orderMidPrice):
        # Get the limitOrderAbsolutePrice
        limitOrderAbsolutePrice = self.base.limitOrderAbsolutePrice
        # Get the minPremium and maxPremium to determine the limit price based on that.
        minPremium = self.base.minPremium
        maxPremium = self.base.maxPremium
        # Get the limitOrderRelativePriceAdjustment
        limitOrderRelativePriceAdjustment = self.base.limitOrderRelativePriceAdjustment or 0.0

        # Compute Limit Order price
        if limitOrderAbsolutePrice is not None:
            if abs(orderMidPrice) < 1e-5:
                limitOrderRelativePriceAdjustment = 0
            else:
                # Compute the relative price adjustment (needed to adjust each leg with the same proportion)
                limitOrderRelativePriceAdjustment = limitOrderAbsolutePrice / orderMidPrice - 1
            # Use the specified absolute price
            limitOrderPrice = limitOrderAbsolutePrice
        else:
            # Set the Limit Order price (including slippage)
            limitOrderPrice = orderMidPrice * (1 + limitOrderRelativePriceAdjustment)

        # Compute the total slippage
        totalSlippage = sum(list(map(abs, sides))) * self.base.slippage
        # Add slippage to the limit order
        limitOrderPrice -= totalSlippage

        # Adjust the limit order price based on minPremium and maxPremium
        if minPremium is not None and limitOrderPrice < minPremium:
            limitOrderPrice = minPremium
        if maxPremium is not None and limitOrderPrice > maxPremium:
            limitOrderPrice = maxPremium

        return limitOrderPrice

    # Create dictionary with the details of the order to be submitted
    def getOrderDetails(self, contracts, sides, strategy, sell=True, strategyId=None, expiry=None, sidesDesc=None):
        # Exit if there are no contracts to process
        if not contracts:
            return

        # Exit if we already have a working order for the same set of contracts and sides
        if self.isDuplicateOrder(contracts, sides):
            return

        # Get the context
        context = self.context

        # Set the Strategy Id (if not specified)
        strategyId = strategyId or strategy.replace(" ", "")

        # Get the Expiration from the first contract (unless otherwise specified
        expiry = expiry or contracts[0].Expiry
        # Get the last trading day for the given expiration date (in case it falls on a holiday)
        expiryLastTradingDay = self.context.lastTradingDay(expiry)
        # Set the date/time threshold by which the position must be closed (on the last trading day before expiration)
        expiryMarketCloseCutoffDttm = None
        if self.base.marketCloseCutoffTime != None:
            expiryMarketCloseCutoffDttm = datetime.combine(expiryLastTradingDay, self.base.marketCloseCutoffTime)
        # Dictionary to map each contract symbol to the side (short/long)
        contractSide = {}
        # Dictionary to map each contract symbol to its description
        contractSideDesc = {}
        # Dictionary to map each contract symbol to the actual contract object
        contractDictionary = {}

        # Dictionaries to keep track of all the strikes, Delta and IV
        strikes = {}
        delta = {}
        gamma = {}
        vega = {}
        theta = {}
        rho = {}
        vomma = {}
        elasticity = {}
        IV = {}
        midPrices = {}
        contractExpiry = {}

        # Compute the Greeks for each contract (if not already available)
        if self.base.computeGreeks:
            self.bsm.setGreeks(contracts)

        # Compute the Mid-Price and Bid-Ask spread for the full order
        orderMidPrice = 0.0
        bidAskSpread = 0.0
        # Get the slippage parameter (if available)
        slippage = self.base.slippage or 0.0

        # Get the maximum order quantity
        maxOrderQuantity = self.getMaxOrderQuantity()
        # Get the targetPremiumPct
        targetPremiumPct = self.base.targetPremiumPct
        # Check if we are using dynamic premium targeting
        if targetPremiumPct != None:
            # Make sure targetPremiumPct is bounded to the range [0, 1])
            targetPremiumPct = max(0.0, min(1.0, targetPremiumPct))
            # Compute the target premium as a percentage of the total net portfolio value
            targetPremium = context.Portfolio.TotalPortfolioValue * targetPremiumPct
        else:
            targetPremium = self.base.targetPremium

        # Check if we have a description for the contracts
        if sidesDesc == None:
            # Temporary dictionaries to lookup a description
            optionTypeDesc = {OptionRight.Put: "Put", OptionRight.Call: "Call"}
            optionSideDesc = {-1: "short", 1: "long"}
            # create a description for each contract: <long|short><Call|Put>
            sidesDesc = list(map(lambda contract, side: f"{optionSideDesc[np.sign(side)]}{optionTypeDesc[contract.Right]}", contracts, sides))

        n = 0
        for contract in contracts:
            # Contract Side: +n -> Long, -n -> Short
            orderSide = sides[n]
            # Contract description (<long|short><Call|Put>)
            orderSideDesc = sidesDesc[n]

            # Store it in the dictionary
            contractSide[contract.Symbol] = orderSide
            contractSideDesc[contract.Symbol] = orderSideDesc
            contractDictionary[contract.Symbol] = contract

            # Set the strike in the dictionary -> "<short|long><Call|Put>": <strike>
            strikes[f"{orderSideDesc}"] = contract.Strike
            # Add the contract expiration time and add 16 hours to the market close
            contractExpiry[f"{orderSideDesc}"] = contract.Expiry + timedelta(hours = 16)
            if hasattr(contract, "BSMGreeks"):
                # Set the Greeks and IV in the dictionary -> "<short|long><Call|Put>": <greek|IV>
                delta[f"{orderSideDesc}"] = contract.BSMGreeks.Delta
                gamma[f"{orderSideDesc}"] = contract.BSMGreeks.Gamma
                vega[f"{orderSideDesc}"] = contract.BSMGreeks.Vega
                theta[f"{orderSideDesc}"] = contract.BSMGreeks.Theta
                rho[f"{orderSideDesc}"] = contract.BSMGreeks.Rho
                vomma[f"{orderSideDesc}"] = contract.BSMGreeks.Vomma
                elasticity[f"{orderSideDesc}"] = contract.BSMGreeks.Elasticity
                IV[f"{orderSideDesc}"] = contract.BSMImpliedVolatility

            # Get the latest mid-price
            midPrice = self.contractUtils.midPrice(contract)
            # Store the midPrice in the dictionary -> "<short|long><Call|Put>": midPrice
            midPrices[f"{orderSideDesc}"] = midPrice
            # Compute the bid-ask spread
            bidAskSpread += self.contractUtils.bidAskSpread(contract)
            # Adjusted mid-price (include slippage). Take the sign of orderSide to determine the direction of the adjustment
            # adjustedMidPrice = midPrice + np.sign(orderSide) * slippage
            # Keep track of the total credit/debit or the order
            orderMidPrice -= orderSide * midPrice

            # Increment counter
            n += 1

        limitOrderPrice = self.limitOrderPrice(sides=sides, orderMidPrice=orderMidPrice)
        # Round the prices to the nearest cent
        orderMidPrice = round(orderMidPrice, 2)
        limitOrderPrice = round(limitOrderPrice, 2)

        # Determine which price is used to compute the order quantity
        if self.base.useLimitOrders:
            # Use the Limit Order price
            qtyMidPrice = limitOrderPrice
        else:
            # Use the contract mid-price
            qtyMidPrice = orderMidPrice

        if targetPremium == None:
            # No target premium was provided. Use maxOrderQuantity
            orderQuantity = maxOrderQuantity
        else:
            # Make sure we are not exceeding the available portfolio margin
            targetPremium = min(context.Portfolio.MarginRemaining, targetPremium)

            # Determine the order quantity based on the target premium
            if abs(qtyMidPrice) <= 1e-5:
                orderQuantity = 1
            else:
                orderQuantity = abs(targetPremium / (qtyMidPrice * 100))

            # Different logic for Credit vs Debit strategies
            if sell:  # Credit order
                # Sell at least one contract
                orderQuantity = max(1, round(orderQuantity))
            else:  # Debit order
                # Make sure the total price does not exceed the target premium
                orderQuantity = math.floor(orderQuantity)

        # Get the current price of the underlying
        security = context.Securities[self.base.underlyingSymbol]
        underlyingPrice = context.GetLastKnownPrice(security).Price

        # Compute MaxLoss
        maxLoss = self.computeOrderMaxLoss(contracts, sides)
        # Get the Profit Target percentage is specified (default is 50%)
        profitTargetPct = self.base.parameter("profitTarget", 0.5)
        # Compute T-Reg margin based on the MaxLoss
        TReg = min(0, orderMidPrice + maxLoss) * orderQuantity

        portfolioMarginStress = self.context.portfolioMarginStress
        if self.base.computeGreeks:
            # Compute the projected P&L of the position following a % movement of the underlying up or down
            portfolioMargin = min(
                0,
                self.fValue(underlyingPrice * (1-portfolioMarginStress), contracts, sides=sides, atTime=context.Time, openPremium=midPrice),
                self.fValue(underlyingPrice * (1+portfolioMarginStress), contracts, sides=sides, atTime=context.Time, openPremium=midPrice)
            ) * orderQuantity

        order = {
            "strategyId": strategyId,
            "expiry": expiry,
            "orderMidPrice": orderMidPrice,
            "limitOrderPrice": limitOrderPrice,
            "bidAskSpread": bidAskSpread,
            "orderQuantity": orderQuantity,
            "maxOrderQuantity": maxOrderQuantity,
            "targetPremium": targetPremium,
            "strikes": strikes,
            "sides": sides,
            "sidesDesc": sidesDesc,
            "contractSide": contractSide,
            "contractSideDesc": contractSideDesc,
            "contracts": contracts,
            "contractExpiry": contractExpiry,
            "creditStrategy": sell,
            "maxLoss": maxLoss,
            "expiryLastTradingDay": expiryLastTradingDay,
            "expiryMarketCloseCutoffDttm": expiryMarketCloseCutoffDttm
        }
        # Create order details
        # order = {"expiry": expiry
        #         , "expiryStr": expiry.strftime("%Y-%m-%d")
        #         , "expiryLastTradingDay": expiryLastTradingDay
        #         , "expiryMarketCloseCutoffDttm": expiryMarketCloseCutoffDttm
        #         , "strategyId": strategyId
        #         , "strategy": strategy
        #         , "sides": sides
        #         , "sidesDesc": sidesDesc
        #         , "contractExpiry": contractExpiry
        #         , "contractSide": contractSide
        #         , "contractSideDesc": contractSideDesc
        #         , "contractDictionary": contractDictionary
        #         , "strikes": strikes
        #         , "midPrices": midPrices
        #         , "delta": delta
        #         , "gamma": gamma
        #         , "vega": vega
        #         , "theta": theta
        #         , "rho": rho
        #         , "vomma": vomma
        #         , "elasticity": elasticity
        #         , "IV": IV
        #         , "contracts": contracts
        #         , "targetPremium": targetPremium
        #         , "maxOrderQuantity": maxOrderQuantity
        #         , "orderQuantity": orderQuantity
        #         , "creditStrategy": sell
        #         , "maxLoss": maxLoss
        #         , "TReg": TReg
        #         , "portfolioMargin": portfolioMargin
        #         , "open": {"orders": []
        #                     , "fills": 0
        #                     , "filled": False
        #                     , "stalePrice": False
        #                     , "orderMidPrice": orderMidPrice
        #                     , "limitOrderPrice": limitOrderPrice
        #                     , "qtyMidPrice": qtyMidPrice
        #                     , "limitOrder": parameters["useLimitOrders"]
        #                     , "limitOrderExpiryDttm": context.Time + parameters["limitOrderExpiration"]
        #                     , "bidAskSpread": bidAskSpread
        #                     , "fillPrice": 0.0
        #                     }
        #         , "close": {"orders": []
        #                     , "fills": 0
        #                     , "filled": False
        #                     , "stalePrice": False
        #                     , "orderMidPrice": 0.0
        #                     , "fillPrice": 0.0
        #                     }
        #         }

        # Determine the method used to calculate the profit target
        profitTargetMethod = self.base.parameter("profitTargetMethod", "Premium").lower()
        thetaProfitDays = self.base.parameter("thetaProfitDays", 0)
        # Set a custom profit target unless we are using the default Premium based methodology
        if profitTargetMethod != "premium":
            if profitTargetMethod == "theta" and thetaProfitDays > 0:
                # Calculate the P&L of the position at T+[thetaProfitDays]
                thetaPnL = self.fValue(underlyingPrice, contracts, sides=sides, atTime=context.Time + timedelta(days=thetaProfitDays), openPremium=midPrice)
                # Profit target is a percentage of the P&L calculated at T+[thetaProfitDays]
                profitTargetAmt = profitTargetPct * abs(thetaPnL) * orderQuantity
            elif profitTargetMethod == "treg":
                # Profit target is a percentage of the TReg requirement
                profitTargetAmt = profitTargetPct * abs(TReg) * orderQuantity
            elif profitTargetMethod == "margin":
                # Profit target is a percentage of the margin requirement
                profitTargetAmt = profitTargetPct * abs(portfolioMargin) * orderQuantity
            else:
                pass
            # Set the target profit for the position
            order["targetProfit"] = profitTargetAmt

        return order

    def getNakedOrder(self, contracts, type, strike = None, delta = None, fromPrice = None, toPrice = None, sell = True):
        if sell:
            # Short option contract
            sides = [-1]
            strategy = f"Short {type.title()}"
        else:
            # Long option contract
            sides = [1]
            strategy = f"Long {type.title()}"

        type = type.lower()
        if type == "put":
            # Get all Puts with a strike lower than the given strike and delta lower than the given delta
            sorted_contracts = self.strategyBuilder.getPuts(contracts, toDelta = delta, toStrike = strike, fromPrice = fromPrice, toPrice = toPrice)
        elif type == "call":
            # Get all Calls with a strike higher than the given strike and delta lower than the given delta
            sorted_contracts = self.strategyBuilder.getCalls(contracts, toDelta = delta, fromStrike = strike, fromPrice = fromPrice, toPrice = toPrice)
        else:
            self.logger.error(f"Input parameter type = {type} is invalid. Valid values: Put|Call.")
            return

        # Check if we got any contracts
        if len(sorted_contracts):
            # Create order details
            order = self.getOrderDetails([sorted_contracts[0]], sides, strategy, sell)
            # Return the order
            return order


    # Create order details for a Straddle order
    def getStraddleOrder(self, contracts, strike = None, netDelta = None, sell = True):

        if sell:
            # Short Straddle
            sides = [-1, -1]
            strategy = "Short Straddle"
        else:
            # Long Straddle
            sides = [1, 1]
            strategy = "Long Straddle"

        # Delta strike selection (in case the Iron Fly is not centered on the ATM strike)
        delta = None
        # Make sure the netDelta is less than 50
        if netDelta != None and abs(netDelta) < 50:
            delta = 50 + netDelta

        if strike == None and delta == None:
            # Standard Straddle: get the ATM contracts
            legs = self.strategyBuilder.getATM(contracts)
        else:
            legs = []
            # This is a Straddle centered at the given strike or Net Delta.
            # Get the Put at the requested delta or strike
            puts = self.strategyBuilder.getPuts(contracts, toDelta = delta, toStrike = strike)
            if(len(puts) > 0):
                put = puts[0]

                # Get the Call at the same strike as the Put
                calls = self.strategyBuilder.getCalls(contracts, fromStrike = put.Strike)
                if(len(calls) > 0):
                    call = calls[0]
                # Collect both legs
                legs = [put, call]

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell)
        # Return the order
        return order


    # Create order details for a Strangle order
    def getStrangleOrder(self, contracts, callDelta = None, putDelta = None, callStrike = None, putStrike = None, sell = True):

        if sell:
            # Short Strangle
            sides = [-1, -1]
            strategy = "Short Strangle"
        else:
            # Long Strangle
            sides = [1, 1]
            strategy = "Long Strangle"

        # Get all Puts with a strike lower than the given putStrike and delta lower than the given putDelta
        puts = self.strategyBuilder.getPuts(contracts, toDelta = putDelta, toStrike = putStrike)
        # Get all Calls with a strike higher than the given callStrike and delta lower than the given callDelta
        calls = self.strategyBuilder.getCalls(contracts, toDelta = callDelta, fromStrike = callStrike)

        # Get the two contracts
        legs = []
        if len(puts) > 0 and len(calls) > 0:
            legs = [puts[0], calls[0]]

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell)
        # Return the order
        return order


    def getSpreadOrder(self, contracts, type, strike = None, delta = None, wingSize = None, sell = True, fromPrice = None, toPrice = None, premiumOrder = "max"):

        if sell:
            # Credit Spread
            sides = [-1, 1]
            strategy = f"{type.title()} Credit Spread"
        else:
            # Debit Spread
            sides = [1, -1]
            strategy = f"{type.title()} Debit Spread"

        # Get the legs of the spread
        legs = self.strategyBuilder.getSpread(contracts, type, strike = strike, delta = delta, wingSize = wingSize, fromPrice = fromPrice, toPrice = toPrice, premiumOrder = premiumOrder)
        self.logger.debug(f"getSpreadOrder -> legs: {legs}")
        self.logger.debug(f"getSpreadOrder -> sides: {sides}")
        self.logger.debug(f"getSpreadOrder -> strategy: {strategy}")
        self.logger.debug(f"getSpreadOrder -> sell: {sell}")
        # Exit if we couldn't get both legs of the spread
        if len(legs) != 2:
            return

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell)
        # Return the order
        return order


    def getIronCondorOrder(self, contracts, callDelta = None, putDelta = None, callStrike = None, putStrike = None, callWingSize = None, putWingSize = None, sell = True):

        if sell:
            # Sell Iron Condor: [longPut, shortPut, shortCall, longCall]
            sides = [1, -1, -1, 1]
            strategy = "Iron Condor"
        else:
            # Buy Iron Condor: [shortPut, longPut, longCall, shortCall]
            sides = [-1, 1, 1, -1]
            strategy = "Reverse Iron Condor"

        # Get the Put spread
        puts = self.strategyBuilder.getSpread(contracts, "Put", strike = putStrike, delta = putDelta, wingSize = putWingSize, sortByStrike = True)
        # Get the Call spread
        calls = self.strategyBuilder.getSpread(contracts, "Call", strike = callStrike, delta = callDelta, wingSize = callWingSize)

        # Collect all legs
        legs = puts + calls

        # Exit if we couldn't get all legs of the Iron Condor
        if len(legs) != 4:
            return

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell)
        # Return the order
        return order


    def getIronFlyOrder(self, contracts, netDelta = None, strike = None, callWingSize = None, putWingSize = None, sell = True):

        if sell:
            # Sell Iron Fly: [longPut, shortPut, shortCall, longCall]
            sides = [1, -1, -1, 1]
            strategy = "Iron Fly"
        else:
            # Buy Iron Fly: [shortPut, longPut, longCall, shortCall]
            sides = [-1, 1, 1, -1]
            strategy = "Reverse Iron Fly"

        # Delta strike selection (in case the Iron Fly is not centered on the ATM strike)
        delta = None
        # Make sure the netDelta is less than 50
        if netDelta != None and abs(netDelta) < 50:
            delta = 50 + netDelta

        if strike == None and delta == None:
            # Standard ATM Iron Fly
            strike = self.strategyBuilder.getATMStrike(contracts)

        # Get the Put spread
        puts = self.strategyBuilder.getSpread(contracts, "Put", strike = strike, delta = delta, wingSize = putWingSize, sortByStrike = True)
        # Get the Call spread with the same strike as the first leg of the Put spread
        calls = self.strategyBuilder.getSpread(contracts, "Call", strike = puts[-1].Strike, wingSize = callWingSize)

        # Collect all legs
        legs = puts + calls

        # Exit if we couldn't get all legs of the Iron Fly
        if len(legs) != 4:
            return

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell)
        # Return the order
        return order


    def getButterflyOrder(self, contracts, type, netDelta = None, strike = None, leftWingSize = None, rightWingSize = None, sell = False):

        # Make sure the wing sizes are set
        leftWingSize = leftWingSize or rightWingSize or 1
        rightWingSize = rightWingSize or leftWingSize or 1

        if sell:
            # Sell Butterfly: [short<Put|Call>, 2 long<Put|Call>, short<Put|Call>]
            sides = [-1, 2, -1]
            strategy = "Credit Butterfly"
        else:
            # Buy Butterfly: [long<Put|Call>, 2 short<Put|Call>, long<Put|Call>]
            sides = [1, -2, 1]
            strategy = "Debit Butterfly"

        # Create a custom description for each side to uniquely identify the wings:
        # Sell Butterfly: [leftShort<Put|Call>, 2 Long<Put|Call>, rightShort<Put|Call>]
        # Buy Butterfly: [leftLong<Put|Call>, 2 Short<Put|Call>, rightLong<Put|Call>]
        optionSides = {-1: "Short", 1: "Long"}
        sidesDesc = list(map(lambda side, prefix: f"{prefix}{optionSides[np.sign(side)]}{type.title()}", sides, ["left", "", "right"]))


        # Delta strike selection (in case the Butterfly is not centered on the ATM strike)
        delta = None
        # Make sure the netDelta is less than 50
        if netDelta != None and abs(netDelta) < 50:
            if type.lower() == "put":
                # Use Put delta
                delta = 50 + netDelta
            else:
                # Use Call delta
                delta = 50 - netDelta

        if strike == None and delta == None:
            # Standard ATM Butterfly
            strike = self.strategyBuilder.getATMStrike(contracts)

        type = type.lower()
        if type == "put":
            # Get the Put spread (sorted by strike in ascending order)
            putSpread = self.strategyBuilder.getSpread(contracts, "Put", strike = strike, delta = delta, wingSize = leftWingSize, sortByStrike = True)
            # Exit if we couldn't get all legs of the Iron Fly
            if len(putSpread) != 2:
                return
            # Get the middle strike (second entry in the list)
            middleStrike = putSpread[1].Strike
            # Find the right wing of the Butterfly (add a small offset to the fromStrike in order to avoid selecting the middle strike as a wing)
            wings = self.strategyBuilder.getPuts(contracts, fromStrike = middleStrike + 0.1, toStrike = middleStrike + rightWingSize)
            # Exit if we could not find the wing
            if len(wings) == 0:
                return
            # Combine all the legs
            legs = putSpread + wings[0]
        elif type == "call":
            # Get the Call spread (sorted by strike in ascending order)
            callSpread = self.strategyBuilder.getSpread(contracts, "Call", strike = strike, delta = delta, wingSize = rightWingSize)
            # Exit if we couldn't get all legs of the Iron Fly
            if len(callSpread) != 2:
                return
            # Get the middle strike (first entry in the list)
            middleStrike = callSpread[0].Strike
            # Find the left wing of the Butterfly (add a small offset to the toStrike in order to avoid selecting the middle strike as a wing)
            wings = self.strategyBuilder.getCalls(contracts, fromStrike = middleStrike - leftWingSize, toStrike = middleStrike - 0.1)
            # Exit if we could not find the wing
            if len(wings) == 0:
                return
            # Combine all the legs
            legs = wings[0] + callSpread
        else:
            self.logger.error(f"Input parameter type = {type} is invalid. Valid values: Put|Call.")
            return

        # Exit if we couldn't get both legs of the spread
        if len(legs) != 3:
            return

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell = sell, sidesDesc = sidesDesc)
        # Return the order
        return order


    def getCustomOrder(self, contracts, types, deltas = None, sides = None, sidesDesc = None, strategy = "Custom", sell = None):

        # Make sure the Sides parameter has been specified
        if not sides:
            self.logger.error("Input parameter sides cannot be null. No order will be returned.")
            return

        # Make sure the Sides and Deltas parameters are of the same length
        if not deltas or len(deltas) != len(sides):
            self.logger.error(f"Input parameters deltas = {deltas} and sides = {sides} must have the same length. No order will be returned.")
            return

        # Convert types into a list if it is a string
        if isinstance(types, str):
            types = [types] * len(sides)

        # Make sure the Sides and Types parameters are of the same length
        if not types or len(types) != len(sides):
            self.logger.error(f"Input parameters types = {types} and sides = {sides} must have the same length. No order will be returned.")
            return

        legs = []
        midPrice = 0
        for side, type, delta in zip(sides, types, deltas):
            # Get all Puts with a strike lower than the given putStrike and delta lower than the given putDelta
            deltaContracts = self.strategyBuilder.getContracts(contracts, type = type, toDelta = delta, reverse = type.lower() == "put")
            # Exit if we could not find the contract
            if not deltaContracts:
                return
            # Append the contract to the list of legs
            legs = legs + [deltaContracts[0]]
            # Update the mid-price
            midPrice -= self.contractUtils.midPrice(deltaContracts[0]) * side

        # Automatically determine if this is a credit or debit strategy (unless specified)
        if sell is None:
            sell = midPrice > 0

        # Create order details
        order = self.getOrderDetails(legs, sides, strategy, sell = sell, sidesDesc = sidesDesc)
        # Return the order
        return order
