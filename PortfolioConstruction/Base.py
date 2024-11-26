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
        if not insights:
            return targets

        for insight in insights:
            # Skip invalid insights
            if insight is None or insight.Id is None or insight.Symbol is None:
                continue

            self.context.logger.debug(f'Insight: {insight.Id}')
            # Let's find the order that this insight belongs to
            order = Helper().findIn(
                self.context.workingOrders.values(),
                lambda v: v is not None and v.insights is not None and any(i is not None and i.Id == insight.Id for i in v.insights))

            # Skip if no matching order is found
            if order is None:
                continue

            # Skip if order ID is not in allPositions
            if order.orderId not in self.context.allPositions:
                continue

            position = self.context.allPositions[order.orderId]

            # Handle None or invalid direction/quantity
            direction = 0 if insight.Direction is None else insight.Direction
            quantity = 0 if position.orderQuantity is None else position.orderQuantity

            target = PortfolioTarget(insight.Symbol, direction * quantity)
            self.context.logger.debug(f'Target: {target.Symbol} {target.Quantity}')
            order.targets.append(target)
            targets.append(target)
        return targets
