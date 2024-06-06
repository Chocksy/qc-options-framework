#region imports
from AlgorithmImports import *
#endregion


class Performance:
    def __init__(self, context):
        self.context = context
        self.logger = self.context.logger
        self.dailyTracking = datetime.now()
        self.seenSymbols = set()
        self.tradedSymbols = set()
        self.chainSymbols = set()
        self.tradedToday = False
        self.tracking = {}

    def endOfDay(self, symbol):
        day_summary = {
            "Time": (datetime.now() - self.dailyTracking).total_seconds(),
            "Portfolio": len(self.context.Portfolio),
            "Invested": sum(1 for kvp in self.context.Portfolio if kvp.Value.Invested),
            "Seen": len(self.seenSymbols),
            "Traded": len(self.tradedSymbols),
            "Chains": len(self.chainSymbols)
        }
            # Convert Symbol instance to string
        symbol_str = str(symbol)
        
        # Ensure the symbol is in the tracking dictionary
        if symbol_str not in self.tracking:
            self.tracking[symbol_str] = {}
        
        # Store the day summary
        self.tracking[self.context.Time.date()][symbol_str] = day_summary
        self.dailyTracking = datetime.now()
        self.tradedToday = False

    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status == OrderStatus.Filled or orderEvent.Status == OrderStatus.PartiallyFilled:
            if orderEvent.Quantity > 0:
                self.logger.trace(f"Filled {orderEvent.Symbol}")
                self.tradedSymbols.add(orderEvent.Symbol)
                self.tradedToday = True
            else:
                self.logger.trace(f"Unwound {orderEvent.Symbol}")

    def OnUpdate(self, data):
        if data.OptionChains:
            for kvp in data.OptionChains:
                chain = kvp.Value  # Access the OptionChain from the KeyValuePair
                self.chainSymbols.update([oc.Symbol for oc in chain])
                if not self.tradedToday:
                    for optionContract in (contract for contract in chain if contract.Symbol not in self.tradedSymbols):
                        self.seenSymbols.add(optionContract.Symbol)

    def show(self, csv=False):
        if csv:
            self.context.Log("Day,Symbol,Time,Portfolio,Invested,Seen,Traded,Chains")
        for day in sorted(self.tracking.keys()):
            for symbol, stats in self.tracking[day].items():
                if csv:
                    self.context.Log(f"{day},{symbol},{stats['Time']},{stats['Portfolio']},{stats['Invested']},{stats['Seen']},{stats['Traded']},{stats['Chains']}")
                else:
                    self.context.Log(f"{day} - {symbol}: {stats}")
