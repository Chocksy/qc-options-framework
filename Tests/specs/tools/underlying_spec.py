from mamba import description, context, it, before
from expects import expect, equal
from unittest.mock import patch
from Tests.spec_helper import patch_imports
from Tests.factories import Factory

with patch_imports()[0], patch_imports()[1]:
    from Tools.Underlying import Underlying

with description('Underlying') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            self.symbol = "TEST"
            self.underlying = Underlying(self.algorithm, self.symbol)

    with context('initialization'):
        with it('sets context and symbol correctly'):
            expect(self.underlying.context).to(equal(self.algorithm))
            expect(self.underlying.underlyingSymbol).to(equal(self.symbol))

    with context('Security'):
        with it('returns the correct security from context'):
            security = self.underlying.Security()
            expect(security).to(equal(self.algorithm.Securities[self.symbol]))

    with context('Price'):
        with it('returns the current price of the security'):
            price = self.underlying.Price()
            expect(price).to(equal(100.0))  # Default mock price from Factory

    with context('Close'):
        with it('returns the close price of the security'):
            close = self.underlying.Close()
            expect(close).to(equal(100.0))  # Default mock price from Factory