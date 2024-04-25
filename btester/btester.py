from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Type, Hashable, Optional
from math import nan, isnan
import pandas as pd

@dataclass
class Position:
    """
    Represents an open financial position.

    Attributes:
    - symbol: Optional[str] - Symbol of the financial instrument.
    - open_date: Optional[datetime] - Date when the position was opened.
    - last_date: Optional[datetime] - Date of the latest update to the position.
    - open_price: float - Price at which the position was opened.
    - last_price: float - Latest market price of the instrument.
    - position_size: float - Size of the position.
    - profit_loss: float - Cumulative profit or loss of the position.
    - change_pct: float - Percentage change in price since opening the position.
    - current_value: float - Current market value of the position.

    Methods:
    - update(last_date: datetime, last_price: float) - Update the position with the latest market data.
    """
    symbol: Optional[str] = None
    open_date: Optional[datetime] = None
    last_date: Optional[datetime] = None
    open_price: float = nan
    last_price: float = nan
    position_size: float = nan
    profit_loss: float = nan
    change_pct: float = nan
    current_value: float = nan

    def update(self, last_date: datetime, last_price: float):
        self.last_date = last_date
        self.last_price = last_price
        self.profit_loss = (self.last_price - self.open_price) * self.position_size
        self.change_pct = (self.last_price / self.open_price - 1) * 100
        self.current_value = self.open_price * self.position_size + self.profit_loss

@dataclass
class Trade:
    """
    Represents a completed financial transaction.

    Attributes:
    - symbol: Optional[str] - Symbol of the financial instrument.
    - open_date: Optional[datetime] - Date when the trade was opened.
    - close_date: Optional[datetime] - Date when the trade was closed.
    - open_price: float - Price at which the trade was opened.
    - close_price: float - Price at which the trade was closed.
    - position_size: float - Size of the traded position.
    - profit_loss: float - Cumulative profit or loss of the trade.
    - change_pct: float - Percentage change in price during the trade.
    - trade_commission: float - Commission paid for the trade.
    - cumulative_return: float - Cumulative return after the trade.
    """
    symbol: Optional[str] = None
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    open_price: float = nan
    close_price: float = nan
    position_size: float = nan
    profit_loss: float = nan
    change_pct: float = nan
    trade_commission: float = nan
    cumulative_return: float = nan

@dataclass
class Result:
    """
    Container class for backtest results.

    Attributes:
    - returns: pd.Series - Time series of cumulative returns.
    - trades: List[Trade] - List of completed trades.
    - open_positions: List[Position] - List of remaining open positions.
    """
    returns: pd.Series
    trades: List[Trade]
    open_positions: List[Position]

class Strategy(ABC):
    """
    Abstract base class for implementing trading strategies.

    Methods:
    - init(self) - Abstract method for initializing resources for the strategy.
    - next(self, i: int, record: Dict[Hashable, Any]) - Abstract method defining the core functionality of the strategy.

    Attributes:
    - data: pd.DataFrame - Historical market data.
    - date: Optional[datetime] - Current date during backtesting.
    - cash: float - Available cash for trading.
    - commission: float - Commission rate for trades.
    - symbols: List[str] - List of symbols in the market data.
    - records: List[Dict[Hashable, Any]] - List of records representing market data.
    - index: List[datetime] - List of dates corresponding to market data.
    - returns: List[float] - List of cumulative returns during backtesting.
    - trades: List[Trade] - List of completed trades during backtesting.
    - open_positions: List[Position] - List of remaining open positions during backtesting.
    - cumulative_return: float - Cumulative return of the strategy.
    - assets_value: float - Market value of open positions.

    Methods:
    - open(self, price: float, size: Optional[float] = None, symbol: Optional[str] = None) -> bool
    - close(self, price: float, symbol: Optional[str] = None, position: Optional[Position] = None) -> bool
    """

    @abstractmethod
    def init(self):
        """
        Abstract method for initializing resources and parameters for the strategy.

        This method is called once at the beginning of the backtest to perform any necessary setup or configuration
        for the trading strategy. It allows the strategy to initialize variables, set parameters, or load external data
        needed for the strategy's functionality.

        Parameters:
        - *args: Additional positional arguments that can be passed during initialization.
        - **kwargs: Additional keyword arguments that can be passed during initialization.

        Example:
        ```python
        def init(self, buy_period: int, sell_period: int):
            self.buy_signal = {}
            self.sell_signal = {}

            for symbol in self.symbols:
                self.buy_signal[symbol] = UpBreakout(self.data[(symbol,'Close')], buy_period)
                self.sell_signal[symbol] = DownBreakout(self.data[(symbol,'Close')], sell_period)
        ```

        Note:
        It is recommended to define the expected parameters and their default values within the `init` method
        to allow flexibility and customization when initializing the strategy.
        """

    @abstractmethod
    def next(self, i: int, record: Dict[Hashable, Any]):
        """
        Abstract method defining the core functionality of the strategy for each time step.

        This method is called iteratively for each time step during the backtest, allowing the strategy to make
        decisions based on the current market data represented by the 'record'. It defines the core logic of the
        trading strategy, such as generating signals, managing positions, and making trading decisions.

        Parameters:
        - i (int): Index of the current time step.
        - record (Dict[Hashable, Any]): Dictionary representing the market data at the current time step.
          The keys can include symbols, and the values can include relevant market data (e.g., OHLC prices).

        Example:
        ```python
        def next(self, i, record):
            for symbol in self.symbols:
                if self.buy_signal[symbol][i-1]:
                    self.open(symbol=symbol, price=record[(symbol,'Open')], size=self.positionSize(record[(symbol,'Open')]))

            for position in self.open_positions[:]:
                if self.sell_signal[position.symbol][i-1]:
                    self.close(position=position, price=record[(position.symbol,'Open')])
        ```
        """

    def __init__(self):
        self.data = pd.DataFrame()
        self.date = None
        self.cash = .0
        self.commission = .0

        self.symbols: List[str] = []

        self.records: List[Dict[Hashable, Any]] = []
        self.index: List[datetime] = []

        self.returns: List[float] = []
        self.trades: List[Trade] = []
        self.open_positions: List[Position] = []

        self.cumulative_return = self.cash
        self.assets_value = .0

    def open(self, price: float, size: Optional[float] = None, symbol: Optional[str] = None):
        """
        Opens a new financial position based on the specified parameters.

        Parameters:
        - price: float - The price at which to open the position.
        - size: Optional[float] - The size of the position. If not provided, it is calculated based on available cash.
        - symbol: Optional[str] - Symbol of the financial instrument.

        Returns:
        - bool: True if the position was successfully opened, False otherwise.

        This method calculates the cost of opening a new position, checks if the specified size is feasible given
        available cash, and updates the strategy's open positions accordingly. It returns True if the position is
        successfully opened, and False otherwise.
        """
        if isnan(price) or price <= 0 or (size is not None and (isnan(size) or size <= .0)):
            return False

        if size is None:
            size = self.cash / (price * (1 + self.commission))
            open_cost = self.cash
        else:
            open_cost = size * price * (1 + self.commission)

        if isnan(size) or size <= .0 or self.cash < open_cost:
            return False

        position = Position(symbol=symbol, open_date=self.date, open_price=price, position_size=size)
        position.update(last_date=self.date, last_price=price)

        self.assets_value += position.current_value
        self.cash -= open_cost

        self.open_positions.extend([position])
        return True

    def close(self, price: float, symbol: Optional[str] = None, position: Optional[Position] = None):
        """
        Closes an existing financial position based on the specified parameters.

        Parameters:
        - price: float - The price at which to close the position.
        - symbol: Optional[str] - Symbol of the financial instrument.
        - position: Optional[Position] - The specific position to close. If not provided, closes all positions for the symbol.

        Returns:
        - bool: True if the position(s) were successfully closed, False otherwise.

        This method calculates the cost of closing a position, updates the strategy's cumulative return, and records the
        trade details. If a specific position is provided, only that position is closed. If no position is specified,
        all open positions for the specified symbol are closed. It returns True if the position(s) is successfully
        closed, and False otherwise.
        """
        if isnan(price) or price <= 0:
            return False

        if position is None:
            for position in self.open_positions[:]:
                if position.symbol == symbol:
                    self.close(position=position, price=price)
        else:
            self.assets_value -= position.current_value
            position.update(last_date=self.date, last_price=price)

            trade_commission = (position.open_price + position.last_price) * position.position_size * self.commission
            self.cumulative_return += position.profit_loss - trade_commission

            trade = Trade(position.symbol, position.open_date, position.last_date, position.open_price,
                position.last_price, position.position_size, position.profit_loss, position.change_pct,
                trade_commission, self.cumulative_return)

            self.trades.extend([trade])
            self.open_positions.remove(position)

            close_cost = position.last_price * position.position_size * self.commission
            self.cash += position.current_value - close_cost

        return True

    def __eval(self, *args, **kwargs):
        self.cumulative_return = self.cash
        self.assets_value = .0

        self.init(*args, **kwargs)

        for i, record in enumerate(self.records):
            self.date = self.index[i]

            self.next(i, record)

            for position in self.open_positions:
                last_price = record[(position.symbol, 'Close')] if (position.symbol, 'Close') in record else record['Close']
                if last_price > 0:
                    position.update(last_date=self.date, last_price=last_price)

            self.assets_value = sum(position.current_value for position in self.open_positions)
            self.returns.append(self.cash + self.assets_value)

        return Result(
            returns=pd.Series(index=self.index, data=self.returns, dtype=float),
            trades=self.trades,
            open_positions=self.open_positions
        )

class Backtest:
    """
    Class for running a backtest on a given strategy using historical market data.

    Attributes:
    - strategy: Type[Strategy] - Type of strategy to be backtested.
    - data: pd.DataFrame - Historical market data.
    - cash: float - Initial cash available for trading.
    - commission: float - Commission rate for trades.

    Methods:
    - run(*args, **kwargs) - Run the backtest and return the results.
    """
    def __init__(self,
                 strategy: Type[Strategy],
                 data: pd.DataFrame,
                 cash: float = 10_000,
                 commission: float = .0
                 ):

        self.strategy = strategy
        self.data = data
        self.cash = cash
        self.commission = commission

        columns = data.columns
        self.symbols = columns.get_level_values(0).unique().tolist() if isinstance(columns, pd.MultiIndex) else []

        self.records = data.to_dict('records')
        self.index = data.index.tolist()

    def run(self, *args, **kwargs):
        strategy = self.strategy()
        strategy.data = self.data
        strategy.cash = self.cash
        strategy.commission = self.commission

        strategy.symbols = self.symbols
        strategy.records = self.records
        strategy.index = self.index

        return strategy._Strategy__eval(*args, **kwargs)