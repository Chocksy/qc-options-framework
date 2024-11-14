from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, be_within
from unittest.mock import patch, MagicMock
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks
from datetime import datetime, timedelta

with patch_imports()[0], patch_imports()[1]:
    from Tools.ContractUtils import ContractUtils
    from Tests.mocks.algorithm_imports import OptionContract

with description('ContractUtils') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.contract_utils = ContractUtils(self.algorithm)
            self.option_contract = Factory.create_option_contract()

    with context('getUnderlyingPrice'):
        with it('returns the last known price of the security'):
            with patch_imports()[0], patch_imports()[1]:
                price = self.contract_utils.getUnderlyingPrice("TEST")
                expect(price).to(equal(100.0))

    with context('getUnderlyingLastPrice'):
        with it('returns the last known price from Securities if available'):
            with patch_imports()[0], patch_imports()[1]:
                price = self.contract_utils.getUnderlyingLastPrice(self.option_contract)
                expect(price).to(equal(100.0))

        with it('returns UnderlyingLastPrice from contract if security not found'):
            with patch_imports()[0], patch_imports()[1]:
                # Create a contract with a symbol not in Securities
                contract = Factory.create_option_contract()
                # Remove the TEST symbol from Securities to force the else path
                self.algorithm.Securities = {}  # Empty the Securities dictionary
                contract._underlying_last_price = 150.0  # Set a different price to verify
                
                price = self.contract_utils.getUnderlyingLastPrice(contract)
                expect(price).to(equal(150.0))  # Should return the contract's UnderlyingLastPrice

    with context('getSecurity'):
        with it('returns security from Securities dictionary if available'):
            with patch_imports()[0], patch_imports()[1]:
                security = self.contract_utils.getSecurity(self.option_contract)
                expect(security.Price).to(equal(100.0))

    with context('midPrice'):
        with it('calculates the mid price correctly'):
            with patch_imports()[0], patch_imports()[1]:
                mid_price = self.contract_utils.midPrice(self.option_contract)
                expect(mid_price).to(equal(1.0))  # (0.95 + 1.05) / 2

    with context('strikePrice'):
        with it('returns the strike price of the contract'):
            with patch_imports()[0], patch_imports()[1]:
                strike = self.contract_utils.strikePrice(self.option_contract)
                expect(strike).to(equal(100.0))

    with context('expiryDate'):
        with it('returns the expiry date of the contract'):
            with patch_imports()[0], patch_imports()[1]:
                expiry = self.contract_utils.expiryDate(self.option_contract)
                # Compare only the date parts, not the exact microseconds
                expect(expiry.date()).to(equal(self.option_contract._expiry.date()))

    with context('volume'):
        with it('returns the trading volume'):
            with patch_imports()[0], patch_imports()[1]:
                volume = self.contract_utils.volume(self.option_contract)
                expect(volume).to(equal(1000))

    with context('openInterest'):
        with it('returns the open interest'):
            with patch_imports()[0], patch_imports()[1]:
                oi = self.contract_utils.openInterest(self.option_contract)
                expect(oi).to(equal(100))

    with context('implied_volatility'):
        with it('returns the implied volatility'):
            with patch_imports()[0], patch_imports()[1]:
                iv = self.contract_utils.implied_volatility(self.option_contract)
                expect(iv).to(equal(0.2))

    with context('greeks'):
        with context('delta'):
            with it('returns the delta'):
                with patch_imports()[0], patch_imports()[1]:
                    delta = self.contract_utils.delta(self.option_contract)
                    expect(delta).to(equal(0.0))

        with context('gamma'):
            with it('returns the gamma'):
                with patch_imports()[0], patch_imports()[1]:
                    gamma = self.contract_utils.gamma(self.option_contract)
                    expect(gamma).to(equal(0.0))

        with context('theta'):
            with it('returns the theta'):
                with patch_imports()[0], patch_imports()[1]:
                    theta = self.contract_utils.theta(self.option_contract)
                    expect(theta).to(equal(0.0))

        with context('vega'):
            with it('returns the vega'):
                with patch_imports()[0], patch_imports()[1]:
                    vega = self.contract_utils.vega(self.option_contract)
                    expect(vega).to(equal(0.0))

        with context('rho'):
            with it('returns the rho'):
                with patch_imports()[0], patch_imports()[1]:
                    rho = self.contract_utils.rho(self.option_contract)
                    expect(rho).to(equal(0.0))

    with context('bid/ask prices'):
        with context('bidPrice'):
            with it('returns the bid price'):
                with patch_imports()[0], patch_imports()[1]:
                    bid = self.contract_utils.bidPrice(self.option_contract)
                    expect(bid).to(equal(0.95))

        with context('askPrice'):
            with it('returns the ask price'):
                with patch_imports()[0], patch_imports()[1]:
                    ask = self.contract_utils.askPrice(self.option_contract)
                    expect(ask).to(equal(1.05))

        with context('bidAskSpread'):
            with it('calculates the bid-ask spread correctly'):
                with patch_imports()[0], patch_imports()[1]:
                    spread = self.contract_utils.bidAskSpread(self.option_contract)
                    # Use a range for floating point comparison
                    expect(spread).to(be_within(0.099, 0.101))