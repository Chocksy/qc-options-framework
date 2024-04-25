#region imports
from AlgorithmImports import *
#endregion

# https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/portfolio-construction/key-concepts
# Portfolio construction scaffolding class; basic method args.
class OptionsPortfolioConstructionModel(PortfolioConstructionModel):
    def __init__(self, context):
        pass

    # Create list of PortfolioTarget objects from Insights
    def CreateTargets(self, algorithm: QCAlgorithm, insights: List[Insight]) -> List[PortfolioTarget]:
        return []

    # Determines if the portfolio should rebalance based on the provided rebalancing func
    def IsRebalanceDue(self, insights: List[Insight], algorithmUtc: datetime) -> bool:
        return True

    # Determines the target percent for each insight
    def DetermineTargetPercent(self, activeInsights: List[Insight]) -> Dict[Insight, float]:
        return {}

    # Gets the target insights to calculate a portfolio target percent for, they will be piped to DetermineTargetPercent()
    def GetTargetInsights(self) -> List[Insight]:
        return []

    # Determine if the portfolio construction model should create a target for this insight
    def ShouldCreateTargetForInsight(self, insight: Insight) -> bool:
        return True

    # OPTIONAL: Security change details
    def OnSecuritiesChanged(self, algorithm: QCAlgorithm, changes: SecurityChanges) -> None:
        # Security additions and removals are pushed here.
        # This can be used for setting up algorithm state.
        # changes.AddedSecurities:
        # changes.RemovedSecurities:
        pass
