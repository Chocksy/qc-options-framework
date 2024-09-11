# region imports
from AlgorithmImports import *
from .Base import Base
from .SPXic1 import SPXic1
from .SPXic2 import SPXic2
# endregion

class Evaluate(Base):
    def __init__(self, context, strategy):
        # have varioous order evaluation per strategy 
        self.spx_eval1 = SPXic1(context, strategy)
        self.spx_eval2 = SPXic2(context, strategy) 
        self.context = context
        self.strategy = strategy
        
    def evaluate_spreads(self, contracts, wingSizes):

        if self.strategy.nameTag=="SPXic":
            return self.spx_eval1.evaluate_spreads(contracts, wingSizes)
        # elif self.strategy.nameTag=="SPXic2":
        #     return self.spx_eval2.evaluate_spreads(contracts, wingSizes)
        
            
