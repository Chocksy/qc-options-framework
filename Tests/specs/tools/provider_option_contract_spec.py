from mamba import description, context, it, before
from expects import expect, equal, be_true, be_none
from unittest.mock import patch, MagicMock
from Tests.spec_helper import patch_imports
from Tests.factories import Factory

with patch_imports()[0], patch_imports()[1]:
    from Tools.ProviderOptionContract import ProviderOptionContract
    from AlgorithmImports import datetime, timedelta

with description('ProviderOptionContract') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.symbol = Factory.create_symbol()
            self.underlying_price = 100.0
            self.contract = ProviderOptionContract(self.symbol, self.underlying_price, self.algorithm)

    with context('initialization'):
        with it('initializes with correct attributes'):
            expect(self.contract.symbol).to(equal(self.symbol))
            expect(self.contract.Symbol).to(equal(self.symbol))
            expect(self.contract.Underlying).to(equal(self.symbol.Underlying))
            expect(self.contract.UnderlyingSymbol).to(equal(self.symbol.Underlying))
            expect(self.contract.ID).to(equal(self.symbol.ID))
            expect(self.contract.UnderlyingLastPrice).to(equal(self.underlying_price))

    with context('Greeks'):
        with before.each:
            self.security = self.algorithm.Securities[self.symbol]
            
        with it('returns zero for missing greek values'):
            # Set all greek values to None to simulate missing values
            self.security.delta = None
            self.security.gamma = None
            self.security.theta = None
            self.security.vega = None
            self.security.rho = None

            expect(self.contract.greeks.delta).to(equal(0))
            expect(self.contract.greeks.gamma).to(equal(0))
            expect(self.contract.greeks.theta).to(equal(0))
            expect(self.contract.greeks.vega).to(equal(0))
            expect(self.contract.greeks.rho).to(equal(0))

        with it('returns correct greek values when available'):
            # Setup mock security with greek values
            self.security.delta = MagicMock(current=MagicMock(value=0.5))
            self.security.gamma = MagicMock(current=MagicMock(value=0.1))
            self.security.theta = MagicMock(current=MagicMock(value=-0.2))
            self.security.vega = MagicMock(current=MagicMock(value=0.3))
            self.security.rho = MagicMock(current=MagicMock(value=0.05))

            expect(self.contract.greeks.delta).to(equal(0.5))
            expect(self.contract.greeks.gamma).to(equal(0.1))
            expect(self.contract.greeks.theta).to(equal(-0.2))
            expect(self.contract.greeks.vega).to(equal(0.3))
            expect(self.contract.greeks.rho).to(equal(0.05))

    with context('contract properties'):
        with before.each:
            self.security = self.algorithm.Securities[self.symbol]
            
        with it('returns correct Expiry'):
            expect(self.contract.Expiry).to(equal(self.symbol.ID.Date))

        with it('returns correct Strike'):
            expect(self.contract.Strike).to(equal(self.symbol.ID.StrikePrice))

        with it('returns correct Right'):
            expect(self.contract.Right).to(equal(self.symbol.ID.OptionRight))

        with it('returns correct price properties'):
            expect(self.contract.BidPrice).to(equal(self.security.BidPrice))
            expect(self.contract.AskPrice).to(equal(self.security.AskPrice))
            expect(self.contract.LastPrice).to(equal(self.security.Price))

        with it('returns correct IsTradable status'):
            expect(self.contract.IsTradable).to(equal(self.security.IsTradable))

        with it('returns correct OpenInterest'):
            expect(self.contract.OpenInterest).to(equal(self.security.OpenInterest))

        with it('returns correct implied volatility'):
            self.security.iv = MagicMock(current=MagicMock(value=0.25))
            expect(self.contract.implied_volatility).to(equal(0.25))

        with it('returns zero for missing implied volatility'):
            self.security.iv = None
            expect(self.contract.implied_volatility).to(equal(0)) 