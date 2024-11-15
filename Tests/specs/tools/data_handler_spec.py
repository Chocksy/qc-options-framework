from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, be_none
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from Tests.mocks.algorithm_imports import (
    SecurityType, Resolution, Symbol, Market, SecuritiesDict
)
from datetime import timedelta, datetime

# First patch all imports using our centralized mock structure
patch_contexts = patch_imports()
with patch_contexts[0], patch_contexts[1]:
    from Tools.DataHandler import DataHandler

with description('DataHandler') as self:
    with before.each:
        # Make Resolution and Symbol available in the test scope
        self.Resolution = Resolution
        self.Symbol = Symbol
        self.Market = Market
        
        with patch_contexts[0], patch_contexts[1]:
            self.algorithm = Factory.create_algorithm()
            self.ticker = "TEST"
            self.strategy = MagicMock(
                dte=30,
                dteWindow=5,
                nStrikesLeft=2,
                nStrikesRight=2,
                useSlice=False,
                optionSymbol=None,
                underlyingSymbol=self.ticker
            )
            self.data_handler = DataHandler(self.algorithm, self.ticker, self.strategy)
            self.algorithm.logger = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.optionContractsSubscriptions = []

    with context('initialization'):
        with it('sets context, ticker and strategy correctly'):
            expect(self.data_handler.context).to(equal(self.algorithm))
            expect(self.data_handler.ticker).to(equal(self.ticker))
            expect(self.data_handler.strategy).to(equal(self.strategy))

    with context('CashTicker'):
        with it('identifies cash indices correctly'):
            data_handler_spx = DataHandler(self.algorithm, "SPX", self.strategy)
            data_handler_vix = DataHandler(self.algorithm, "VIX", self.strategy)
            data_handler_ndx = DataHandler(self.algorithm, "NDX", self.strategy)
            
            expect(data_handler_spx._DataHandler__CashTicker()).to(be_true)
            expect(data_handler_vix._DataHandler__CashTicker()).to(be_true)
            expect(data_handler_ndx._DataHandler__CashTicker()).to(be_true)
            expect(self.data_handler._DataHandler__CashTicker()).to(be_false)

    with context('AddUnderlying'):
        with it('adds equity for non-cash tickers'):
            self.data_handler.AddUnderlying()
            self.algorithm.AddEquity.assert_called_with(self.ticker, resolution=self.Resolution.Minute)

        with it('adds index for cash tickers'):
            data_handler_spx = DataHandler(self.algorithm, "SPX", self.strategy)
            data_handler_spx.AddUnderlying()
            self.algorithm.AddIndex.assert_called_with("SPX", resolution=self.Resolution.Minute)

    with context('AddOptionsChain'):
        with before.each:
            self.underlying = MagicMock()
            self.underlying.Symbol = Factory.create_symbol()

        with it('adds SPXW options for SPX ticker'):
            data_handler_spx = DataHandler(self.algorithm, "SPX", self.strategy)
            data_handler_spx.AddOptionsChain(self.underlying)
            self.algorithm.AddIndexOption.assert_called_with(self.underlying.Symbol, "SPXW", self.Resolution.Minute)

        with it('adds index options for cash tickers'):
            data_handler_vix = DataHandler(self.algorithm, "VIX", self.strategy)
            data_handler_vix.AddOptionsChain(self.underlying)
            self.algorithm.AddIndexOption.assert_called_with(self.underlying.Symbol, self.Resolution.Minute)

        with it('adds equity options for non-cash tickers'):
            self.data_handler.AddOptionsChain(self.underlying)
            self.algorithm.AddOption.assert_called_with(self.underlying.Symbol, self.Resolution.Minute)

    with context('SetOptionFilter'):
        with it('applies correct filter parameters'):
            universe = MagicMock()
            filtered_universe = MagicMock()
            
            # Setup the method chain
            universe.Strikes.return_value = universe
            universe.Expiration.return_value = universe
            universe.IncludeWeeklys.return_value = filtered_universe
            
            result = self.data_handler.SetOptionFilter(universe)
            
            universe.Strikes.assert_called_with(-self.strategy.nStrikesLeft, self.strategy.nStrikesRight)
            universe.Expiration.assert_called_with(25, 30)  # dte=30, dteWindow=5
            universe.IncludeWeeklys.assert_called_once()
            expect(result).to(equal(filtered_universe))

    with context('optionChainProviderFilter'):
        with before.each:
            self.algorithm.timeResolution = self.Resolution.Minute
            
            # Create proper Symbol mocks for the test contracts
            self.symbol1 = Factory.create_symbol("TEST1")
            self.symbol2 = Factory.create_symbol("TEST2")
            
            # Create a custom __eq__ method for the symbols to handle dictionary lookup
            self.symbol1.__eq__ = lambda x: str(x) == str(self.symbol1)
            self.symbol2.__eq__ = lambda x: str(x) == str(self.symbol2)
            self.symbol1.__hash__ = lambda: hash(str(self.symbol1))
            self.symbol2.__hash__ = lambda: hash(str(self.symbol2))
            
            self.symbols = [
                MagicMock(
                    ID=MagicMock(
                        Date=self.algorithm.Time + timedelta(days=30),
                        StrikePrice=100,
                        Symbol=self.symbol1
                    ),
                    Value=self.symbol1,
                    Underlying=self.symbol1,
                    __str__=lambda x: str(self.symbol1)
                ),
                MagicMock(
                    ID=MagicMock(
                        Date=self.algorithm.Time + timedelta(days=25),
                        StrikePrice=110,
                        Symbol=self.symbol2
                    ),
                    Value=self.symbol2,
                    Underlying=self.symbol2,
                    __str__=lambda x: str(self.symbol2)
                )
            ]
            
            # Mock the Securities dictionary with all required symbols
            self.algorithm.Securities = SecuritiesDict({
                str(self.symbol1): MagicMock(Price=100.0, IsTradable=True),
                str(self.symbol2): MagicMock(Price=110.0, IsTradable=True),
                "TEST": MagicMock(Price=100.0, IsTradable=True)
            })

        with it('filters contracts by date and strike correctly'):
            result = self.data_handler.optionChainProviderFilter(
                self.symbols, -2, 2, 25, 30
            )
            
            expect(result).to(have_length(2))
            self.algorithm.executionTimer.start.assert_called()
            self.algorithm.executionTimer.stop.assert_called()

        with it('returns None when no symbols provided'):
            result = self.data_handler.optionChainProviderFilter(
                [], -2, 2, 25, 30
            )
            expect(result).to(be_none)

    with context('getOptionContracts'):
        with before.each:
            self.algorithm.OptionChainProvider = MagicMock()
            self.algorithm.timeResolution = self.Resolution.Minute
            
            # Create proper symbols for provider path with custom equality
            self.test_symbol = Factory.create_symbol("TEST1")
            self.test_symbol.__eq__ = lambda self, x: str(self) == str(x)
            self.test_symbol.__hash__ = lambda self: hash(str(self))
            self.test_symbol.__str__ = lambda self: "TEST1"
            
            # Set up proper time objects
            self.current_time = datetime.now()
            self.expiry_time = self.current_time + timedelta(days=30)
            self.algorithm.Time = self.current_time
            
            self.test_symbols = [
                MagicMock(
                    ID=MagicMock(
                        Date=self.expiry_time,
                        StrikePrice=100,
                        Symbol=self.test_symbol
                    ),
                    Value=self.test_symbol,
                    Underlying=self.test_symbol,
                    __str__=lambda self: str(self.Value)
                )
            ]
            
            # Use the custom Securities dictionary
            self.algorithm.Securities = SecuritiesDict({
                str(self.test_symbol): MagicMock(Price=100.0, IsTradable=True),
                "TEST": MagicMock(Price=100.0, IsTradable=True)
            })
            
            # For slice test - properly mock the Expiry date operations
            expiry_date = self.expiry_time.date()
            mock_date = MagicMock()
            mock_date.date.return_value = expiry_date
            
            self.contract = MagicMock(
                Symbol=self.test_symbol,
                ID=MagicMock(
                    Date=self.expiry_time,
                    StrikePrice=100
                ),
                Value=self.test_symbol,
                Underlying=self.test_symbol,
                Expiry=mock_date  # Use the properly mocked date object
            )

        with it('gets contracts from slice when useSlice is True'):
            self.strategy.useSlice = True
            self.strategy.optionSymbol = self.test_symbol
            slice = MagicMock()
            
            # Create a proper chain structure
            chain = MagicMock()
            chain.Key = self.test_symbol
            chain.Value = MagicMock()
            chain.Value.Contracts = MagicMock(Count=1)
            # Make sure we return our properly mocked contract
            chain.Value.__iter__ = lambda self: iter([self.parent.contract])
            chain.Value.parent = self
            
            # Make OptionChains iterable and return our chain
            slice.OptionChains = [chain]
            
            result = self.data_handler.getOptionContracts(slice)
            expect(result).to(have_length(1))

        with it('gets contracts from provider when useSlice is False'):
            # Setup the provider to return our test symbols
            self.algorithm.OptionChainProvider.GetOptionContractList.return_value = self.test_symbols
            
            result = self.data_handler.getOptionContracts()
            
            self.algorithm.OptionChainProvider.GetOptionContractList.assert_called_once()
            expect(result).to(have_length(1))

    with context('AddOptionContracts'):
        with before.each:
            self.contracts = [Factory.create_symbol(), Factory.create_symbol()]

        with it('adds index option contracts for cash tickers'):
            data_handler_spx = DataHandler(self.algorithm, "SPX", self.strategy)
            data_handler_spx.AddOptionContracts(self.contracts)
            
            expect(self.algorithm.AddIndexOptionContract.call_count).to(equal(2))
            expect(self.algorithm.optionContractsSubscriptions).to(have_length(2))

        with it('adds equity option contracts for non-cash tickers'):
            self.data_handler.AddOptionContracts(self.contracts)
            
            expect(self.algorithm.AddOptionContract.call_count).to(equal(2))
            expect(self.algorithm.optionContractsSubscriptions).to(have_length(2))

    with context('OptionsContract'):
        with before.each:
            # Reset the mock before each test
            self.Symbol.create_canonical_option.reset_mock()

        with it('creates correct canonical option symbol for SPX'):
            data_handler_spx = DataHandler(self.algorithm, "SPX", self.strategy)
            data_handler_spx.OptionsContract("SPX")
            self.Symbol.create_canonical_option.assert_called_with(
                "SPX", "SPXW", self.Market.USA, "?SPXW"
            )

        with it('creates correct canonical option symbol for other tickers'):
            self.data_handler.OptionsContract("TEST")
            self.Symbol.create_canonical_option.assert_called_with(
                "TEST", self.Market.USA, "?TEST"
            )

    def cleanup(self):
        ModuleMocks.cleanup()