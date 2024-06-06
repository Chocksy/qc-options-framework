#region imports
from AlgorithmImports import *
#endregion

from Tools import Helper

# https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/portfolio-construction/key-concepts
# Portfolio construction scaffolding class; basic method args.
class Base(PortfolioConstructionModel):
    def __init__(self, context):
        self.context = context
        self.context.logger.debug(f"{self.__class__.__name__} -> __init__")

    # Create list of PortfolioTarget objects from Insights
    def CreateTargets(self, algorithm: QCAlgorithm, insights: List[Insight]) -> List[PortfolioTarget]:
        # super().CreateTargets(algorithm, insights)
        targets = []
        for insight in insights:
            self.context.logger.debug(f'Insight: {insight.Id}')
            # Let's find the order that this insight belongs to
            order = Helper().findIn(
                self.context.workingOrders.values(),
                lambda v: any(i.Id == insight.Id for i in v.insights))

            position = self.context.allPositions[order.orderId]

            target = PortfolioTarget(insight.Symbol, insight.Direction * position.orderQuantity)
            self.context.logger.debug(f'Target: {target.Symbol} {target.Quantity}')
            order.targets.append(target)
            targets.append(target)
        return targets

    # Determines if the portfolio should rebalance based on the provided rebalancing func
    # def IsRebalanceDue(self, insights: List[Insight], algorithmUtc: datetime) -> bool:
    #     return True

    # # Determines the target percent for each insight
    # def DetermineTargetPercent(self, activeInsights: List[Insight]) -> Dict[Insight, float]:
    #     return {}

    # # Gets the target insights to calculate a portfolio target percent for, they will be piped to DetermineTargetPercent()
    # def GetTargetInsights(self) -> List[Insight]:
    #     return []

    # # Determine if the portfolio construction model should create a target for this insight
    # def ShouldCreateTargetForInsight(self, insight: Insight) -> bool:
    #     return True

    # OPTIONAL: Security change details
    # def OnSecuritiesChanged(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
    #     # Security additions and removals are pushed here.
    #     # This can be used for setting up algorithm state.
    #     # changes.AddedSecurities:
    #     # changes.RemovedSecurities:
    #     pass
