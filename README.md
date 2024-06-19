# [QC](https://quantconnect.com) options framework/algo
Options framework that allows for an easier implementation of option strategies using QuantConnect's Lean.

## Setup

In order to make this easier you need to have quantconnect running on local dev. That means 

1. Create a new quant connect algorithm. 
2. Clone this repository
3. Install the quantconnect [extension](https://marketplace.visualstudio.com/items?itemName=quantconnect.quantconnect) on VSCode and setup your env
4. Open your newly created algorithm on your local environment
5. Copy all the files from the cloned repo to this quantconnect algo
6. Start creating your own AlphaModel, MonitorModel and ExecutionModel (optional)


## Some explanation of how it works

- each of the folders Alpha, Execution, Monitor, PortfolioConstruction have a Base.py class.
- when you want to use a new strategy you should/can create a new file that inherits from those Base.py classes
- examples of classes/strategies: [Alpha/SPXic.py](https://github.com/Chocksy/qc-options-framework/blob/main/Alpha/SPXic.py), [Monitor/SPXicMonitor.py](https://github.com/Chocksy/qc-options-framework/blob/main/Monitor/SPXicMonitor.py), [Execution/SPXExecutionModel.py](https://github.com/Chocksy/qc-options-framework/blob/main/Execution/SPXExecutionModel.py)
- each of the Base.py classes have some **DEFAULT_PARAMETERS** with comments as to what each of those do.
- when you inherit from the Base classes you can change the **DEFAULT_PARAMETERS** values by definiing a **PARAMETERS** class variable
- at the end you just have to set those new classes you made in [main.py](https://github.com/Chocksy/qc-options-framework/blob/main/main.py) to be used.
- the system is not 100% Algo Framework so its a **hybrid**. That means I hold positions in **self.context.allPositions**, open positions in **self.context.openPositions**, working orders in **self.context.workingOrders**.
- you can see the initial variables attached to **self.context** (that is actually the algorithm instance) by going to [SetupBaseStructure.py](https://github.com/Chocksy/qc-options-framework/blob/main/Initialization/SetupBaseStructure.py)
- all the positions are instances of [Strategy/Position.py](https://github.com/Chocksy/qc-options-framework/blob/main/Strategy/Position.py) a dataclass with defined attributes
- the [Strategy/Position.py](https://github.com/Chocksy/qc-options-framework/blob/main/Strategy/Position.py) also holds dataclasses for WorkingOrders and Legs.


## Notes

This whole code started from the [rccannizzaro](https://github.com/rccannizzaro/QC-StrategyBacktest?tab=readme-ov-file) repository and the amazing work done there. I started tinkering with it and then eventually hit the limit of over 250+ lines for one file on QC so then it evolved into this one.
The code here seems like it follows the principle layed down by QC in their lean framework documentation but in fact there is no 100% separation of concern as we have the communication between classes done via a dataclass of trades and positions. The reason for this is the fact that QC does not allow for more details to be added to Insights and in order to get better management and control we need to just use our own positions dataclass.

