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

## Notes

This whole code started from the [rccannizzaro](https://github.com/rccannizzaro/QC-StrategyBacktest?tab=readme-ov-file) repository and the amazing work done there. I started tinkering with it and then eventually hit the limit of over 250+ lines for one file on QC so then it evolved into this one.
The code here seems like it follows the principle layed down by QC in their lean framework documentation but in fact there is no 100% separation of concern as we have the communication between classes done via a dataclass of trades and positions. The reason for this is the fact that QC does not allow for more details to be added to Insights and in order to get better management and control we need to just use our own positions dataclass.
