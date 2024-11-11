from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false
from unittest.mock import patch, MagicMock
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Patch all Tools modules to avoid circular imports
with patch.dict('sys.modules', ModuleMocks.get_all()):
    with patch_imports()[0], patch_imports()[1]:
        from Strategy.Position import Position, Leg
        from AlgorithmImports import OptionContract, Symbol

with description('Position utility methods') as self:
    with before.each:
        # Patch all Tools modules inside the test context
        with patch.dict('sys.modules', ModuleMocks.get_all()):
            with patch_imports()[0], patch_imports()[1]:
                # Create a position with legs
                self.position = Position(
                    orderId="123",
                    orderTag="TEST_ORDER",
                    strategy="TestStrategy",
                    strategyTag="TEST",
                    expiryStr="20240101"
                )
                
                # Create a symbol with Underlying property
                symbol_mock = MagicMock()
                symbol_mock.Underlying = "TEST"
                
                # Create and add legs to position
                leg = Leg(
                    key="leg1",
                    symbol=symbol_mock,  # Use the mock symbol directly
                    quantity=1,
                    strike=100.0,
                    contract=None  # Contract not needed for this test
                )
                self.position.legs.append(leg)

    with it('returns correct underlying symbol'):
        expect(self.position.underlyingSymbol()).to(equal("TEST"))