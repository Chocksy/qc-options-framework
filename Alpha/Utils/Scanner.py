#region imports
from AlgorithmImports import *
#endregion

from Tools import BSM, Logger

class Scanner:
    def __init__(self, context, base):
        self.context = context
        self.base = base
        # Initialize the BSM pricing model
        self.bsm = BSM(context)
        # Dictionary to keep track of all the available expiration dates at any given date
        self.expiryList = {}
        # Set the logger
        self.logger = Logger(context, className = type(self).__name__, logLevel = context.logLevel)

    def Call(self, data) -> [Dict, str]:
        # Start the timer
        self.context.executionTimer.start('Alpha.Utils.Scanner -> Call')
        self.logger.debug(f'{self.base.name} -> Call -> start')
        if self.isMarketClosed():
            self.logger.trace(" -> Market is closed.")
            return None, None
        self.logger.debug(f'Market not closed')
        if not self.isWithinScheduledTimeWindow():
            self.logger.trace(" -> Not within scheduled time window.")
            return None, None
        self.logger.debug(f'Not within scheduled time window')
        if self.hasReachedMaxActivePositions():
            self.logger.trace(" -> Already reached max active positions.")
            return None, None
        self.logger.debug(f'Reached max active positions')
        # Get the option chain 
        chain = self.base.dataHandler.getOptionContracts(data)
        print(f'Number of contracts in chain: {len(chain) if chain else 0}')
        # Exit if we got no chains
        if chain is None:
            self.logger.debug(" -> No chains inside currentSlice!")
            return None, None
        self.logger.debug('We have chains inside currentSlice')
        self.syncExpiryList(chain)
        self.logger.debug(f'Expiry List: {self.expiryList}')
        # Exit if we haven't found any Expiration cycles to process
        if not self.expiryList:
            self.logger.trace(" -> No expirylist.")
            return None, None
        self.logger.debug('No expirylist')
        # Run the strategy
        filteredChain, lastClosedOrderTag = self.Filter(chain)
        self.logger.debug(f'Filtered Chain Count: {len(filteredChain) if filteredChain else 0}')
        self.logger.debug(f'Last Closed Order Tag: {lastClosedOrderTag}')
        # Stop the timer
        self.context.executionTimer.stop('Alpha.Utils.Scanner -> Call')
        return filteredChain, lastClosedOrderTag

    # Filter the contracts to buy and sell based on the defined AlphaModel/Strategy
    def Filter(self, chain):
        # Start the timer
        self.context.executionTimer.start("Alpha.Utils.Scanner -> Filter")

        # Get the context
        context = self.context
        self.logger.debug(f'Context: {context}')
        # DTE range
        dte = self.base.dte
        dteWindow = self.base.dteWindow

        # Controls whether to select the furthest or the earliest expiry date
        useFurthestExpiry = self.base.useFurthestExpiry
        # Controls whether to enable dynamic selection of the expiry date
        dynamicDTESelection = self.base.dynamicDTESelection
        # Controls whether to allow multiple entries for the same expiry date
        allowMultipleEntriesPerExpiry = self.base.allowMultipleEntriesPerExpiry
        self.logger.debug(f'Allow Multiple Entries Per Expiry: {allowMultipleEntriesPerExpiry}')
        # Set the DTE range (make sure values are not negative)
        minDte = max(0, dte - dteWindow)
        maxDte = max(0, dte)
        self.logger.debug(f'Min DTE: {minDte}')
        self.logger.debug(f'Max DTE: {maxDte}')
        # Get the minimum time distance between consecutive trades
        minimumTradeScheduleDistance = self.base.parameter("minimumTradeScheduleDistance", timedelta(hours=0))
        # Make sure the minimum required amount of time has passed since the last trade was opened
        if (self.context.lastOpenedDttm is not None and context.Time < (self.context.lastOpenedDttm + minimumTradeScheduleDistance)):
            return None, None
        self.logger.debug(f'Min Trade Schedule Distance: {minimumTradeScheduleDistance}')
        # Check if the expiryList was specified as an input
        if self.expiryList is None:
            # List of expiry dates, sorted in reverse order
            self.expiryList = sorted(set([
                contract.Expiry for contract in chain
                if minDte <= (contract.Expiry.date() - context.Time.date()).days <= maxDte
            ]), reverse=True)
            self.logger.debug(f'Expiry List: {self.expiryList}')
            # Log the list of expiration dates found in the chain
            self.logger.debug(f"Expiration dates in the chain: {len(self.expiryList)}")
            for expiry in self.expiryList:
                self.logger.debug(f" -> {expiry}")
        self.logger.debug(f'Expiry List: {self.expiryList}')
        # Exit if we haven't found any Expiration cycles to process
        if not self.expiryList:
            # Stop the timer
            self.context.executionTimer.stop()
            return None, None
        self.logger.debug('No expirylist')
        # Get the DTE of the last closed position
        lastClosedDte = None
        lastClosedOrderTag = None
        if self.context.recentlyClosedDTE:
            while (self.context.recentlyClosedDTE):
                # Pop the oldest entry in the list (FIFO)
                lastClosedTradeInfo = self.context.recentlyClosedDTE.pop(0)
                if lastClosedTradeInfo["closeDte"] >= minDte:
                    lastClosedDte = lastClosedTradeInfo["closeDte"]
                    lastClosedOrderTag = lastClosedTradeInfo["orderTag"]
                    # We got a good entry, get out of the loop
                    break
        self.logger.debug(f'Last Closed DTE: {lastClosedDte}')
        self.logger.debug(f'Last Closed Order Tag: {lastClosedOrderTag}')
        # Check if we need to do dynamic DTE selection
        if dynamicDTESelection and lastClosedDte is not None:
            # Get the expiration with the nearest DTE as that of the last closed position
            expiry = sorted(self.expiryList,
                            key=lambda expiry: abs((expiry.date(
                            ) - context.Time.date()).days - lastClosedDte),
                            reverse=False)[0]
        else:
            # Determine the index used to select the expiry date:
            # useFurthestExpiry = True -> expiryListIndex = 0 (takes the first entry -> furthest expiry date since the expiry list is sorted in reverse order)
            # useFurthestExpiry = False -> expiryListIndex = -1 (takes the last entry -> earliest expiry date since the expiry list is sorted in reverse order)
            expiryListIndex = int(useFurthestExpiry) - 1
            # Get the expiry date
            expiry = list(self.expiryList.keys())[expiryListIndex]
        self.logger.debug(f'Expiry: {expiry}')
        # Convert the date to a string
        expiryStr = expiry.strftime("%Y-%m-%d")

        filteredChain = None
        openPositionsExpiries = [self.context.allPositions[orderId].expiryStr for orderId in self.context.openPositions.values()]
        # Proceed if we have not already opened a position on the given expiration (unless we are allowed to open multiple positions on the same expiry date)
        if (allowMultipleEntriesPerExpiry or expiryStr not in openPositionsExpiries):
            # Filter the contracts in the chain, keep only the ones expiring on the given date
            filteredChain = self.filterByExpiry(chain, expiry=expiry)
        self.logger.debug(f'Number of items in Filtered Chain: {len(filteredChain) if filteredChain else 0}')
        # Stop the timer
        self.context.executionTimer.stop("Alpha.Utils.Scanner -> Filter")

        return filteredChain, lastClosedOrderTag

    def isMarketClosed(self) -> bool:
        # Exit if the algorithm is warming up or the market is closed
        return self.context.IsWarmingUp or not self.context.IsMarketOpen(self.base.underlyingSymbol)

    def isWithinScheduledTimeWindow(self) -> bool:
        # Compute the schedule start datetime
        scheduleStartDttm = datetime.combine(self.context.Time.date(), self.base.scheduleStartTime)
        self.logger.debug(f'Schedule Start Datetime: {scheduleStartDttm}')

        # Exit if we have not reached the schedule start datetime
        if self.context.Time < scheduleStartDttm:
            self.logger.debug('Current time is before the schedule start datetime')
            return False

        # Check if we have a schedule stop datetime
        if self.base.scheduleStopTime is not None:
            # Compute the schedule stop datetime
            scheduleStopDttm = datetime.combine(self.context.Time.date(), self.base.scheduleStopTime)
            self.logger.debug(f'Schedule Stop Datetime: {scheduleStopDttm}')
            # Exit if we have exceeded the stop datetime
            if self.context.Time > scheduleStopDttm:
                self.logger.debug('Current time is after the schedule stop datetime')
                return False

        minutesSinceScheduleStart = round((self.context.Time - scheduleStartDttm).seconds / 60)
        self.logger.debug(f'Minutes Since Schedule Start: {minutesSinceScheduleStart}')
        scheduleFrequencyMinutes = round(self.base.scheduleFrequency.seconds / 60)
        self.logger.debug(f'Schedule Frequency Minutes: {scheduleFrequencyMinutes}')

        # Exit if we are not at the right scheduled interval
        isWithinWindow = minutesSinceScheduleStart % scheduleFrequencyMinutes == 0
        self.logger.debug(f'Is Within Scheduled Time Window: {isWithinWindow}')
        return isWithinWindow

    def hasReachedMaxActivePositions(self) -> bool:
        # Filter openPositions and workingOrders by strategyTag
        openPositionsByStrategy = {tag: pos for tag, pos in self.context.openPositions.items() if self.context.allPositions[pos].strategyTag == self.base.nameTag}
        workingOrdersByStrategy = {tag: order for tag, order in self.context.workingOrders.items() if order.strategyTag == self.base.nameTag}

        # Do not open any new positions if we have reached the maximum for this strategy
        return (len(openPositionsByStrategy) + len(workingOrdersByStrategy)) >= self.base.maxActivePositions

    def syncExpiryList(self, chain):
        # The list of expiry dates will change once a day (at most). See if we have already processed this list for the current date
        if self.context.Time.date() in self.expiryList:
            # Get the expiryList from the dictionary
            expiry = self.expiryList.get(self.context.Time.date())
        else:
            # Start the timer
            self.context.executionTimer.start("Alpha.Utils.Scanner -> syncExpiryList")

            # Set the DTE range (make sure values are not negative)
            minDte = max(0, self.base.dte - self.base.dteWindow)
            maxDte = max(0, self.base.dte)
            # Get the list of expiry dates, sorted in reverse order
            expiry = sorted(
                set(
                    [contract.Expiry for contract in chain if minDte <= (contract.Expiry.date() - self.context.Time.date()).days <= maxDte]
                ),
                reverse=True
            )
            # Only add the list to the dictionary if we found at least one expiry date
            if expiry:
                # Add the list to the dictionary
                self.expiryList[self.context.Time.date()] = expiry
            else:
                self.logger.debug(f"No expiry dates found in the chain! {self.context.Time.strftime('%Y-%m-%d %H:%M')}')}}")

            # Stop the timer
            self.context.executionTimer.stop("Alpha.Utils.Scanner -> syncExpiryList")

    def filterByExpiry(self, chain, expiry=None, computeGreeks=False):
        # Start the timer
        self.context.executionTimer.start("Alpha.Utils.Scanner -> filterByExpiry")

        # Check if the expiry date has been specified
        if expiry is not None:
            # Filter contracts based on the requested expiry date
            filteredChain = [
                contract for contract in chain if contract.Expiry.date() == expiry
            ]
        else:
            # No filtering
            filteredChain = chain

        # Check if we need to compute the Greeks for every single contract (this is expensive!)
        # By default, the Greeks are only calculated while searching for the strike with the
        # requested delta, so there should be no need to set computeGreeks = True
        if computeGreeks:
            self.bsm.setGreeks(filteredChain)

        # Stop the timer
        self.context.executionTimer.stop("Alpha.Utils.Scanner -> filterByExpiry")

        # Return the filtered contracts
        return filteredChain

