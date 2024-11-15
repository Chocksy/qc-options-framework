from mamba import description, context, it, before
from expects import expect, equal, be_true, be_false, contain, have_length, have_key, be_none, be_below
from unittest.mock import patch, MagicMock, call
from Tests.spec_helper import patch_imports
from Tests.factories import Factory
from Tests.mocks.module_mocks import ModuleMocks

# Import after patching
with patch_imports()[0], patch_imports()[1]:
    from Order.OrderBuilder import OrderBuilder
    from Tests.mocks.algorithm_imports import (
        OptionRight, Symbol, datetime, timedelta,
        OptionContract, Resolution
    )

with description('OrderBuilder') as self:
    with before.each:
        with patch_imports()[0], patch_imports()[1]:
            self.algorithm = Factory.create_algorithm()
            
            # Mock common attributes
            self.algorithm.logger = MagicMock()
            self.algorithm.executionTimer = MagicMock()
            self.algorithm.Portfolio = MagicMock()
            
            # Add required attributes for BSM initialization
            self.algorithm.riskFreeRate = 0.02
            self.algorithm.portfolioMarginStress = 0.12  # Also needed for BSM
            
            # Create the OrderBuilder instance
            self.builder = OrderBuilder(self.algorithm)
            
            # Create mock contract
            self.mock_contract = OptionContract()
            self.mock_contract._strike = 100.0
            self.mock_contract._right = OptionRight.Call
            self.mock_contract._expiry = datetime.now() + timedelta(days=30)
            self.mock_contract._bid_price = 0.95
            self.mock_contract._ask_price = 1.05
            self.mock_contract._last_price = 1.0
            self.mock_contract._underlying_last_price = 100.0
            
            # Mock BSM methods
            self.builder.bsm.setGreeks = MagicMock()
            self.builder.bsm.bsmPrice = MagicMock(return_value=1.0)
            
            # Mock contract utils methods
            self.builder.contractUtils.midPrice = MagicMock(return_value=1.0)
            self.builder.contractUtils.bidAskSpread = MagicMock(return_value=0.1)
            self.builder.contractUtils.getUnderlyingLastPrice = MagicMock(return_value=100.0)
            self.builder.contractUtils.getSecurity = MagicMock(return_value=MagicMock(IsTradable=True))

    with context('initialization'):
        with it('initializes with correct attributes'):
            expect(self.builder.context).to(equal(self.algorithm))
            expect(hasattr(self.builder, 'bsm')).to(be_true)
            expect(hasattr(self.builder, 'logger')).to(be_true)
            expect(hasattr(self.builder, 'contractUtils')).to(be_true)

    with context('optionTypeFilter'):
        with it('filters call options correctly'):
            result = self.builder.optionTypeFilter(self.mock_contract, "call")
            expect(result).to(be_true)
            
            self.mock_contract._right = OptionRight.Put
            result = self.builder.optionTypeFilter(self.mock_contract, "call")
            expect(result).to(be_false)

        with it('filters put options correctly'):
            self.mock_contract._right = OptionRight.Put
            result = self.builder.optionTypeFilter(self.mock_contract, "put")
            expect(result).to(be_true)
            
            self.mock_contract._right = OptionRight.Call
            result = self.builder.optionTypeFilter(self.mock_contract, "put")
            expect(result).to(be_false)

        with it('returns true when no type specified'):
            result = self.builder.optionTypeFilter(self.mock_contract)
            expect(result).to(be_true)

    with context('getATM'):
        with before.each:
            # Create list of mock contracts at different strikes
            self.contracts = []
            for strike in [95, 100, 105]:
                contract = OptionContract()
                contract._strike = strike
                contract._right = OptionRight.Call
                self.contracts.append(contract)

        with it('returns ATM contracts correctly'):
            # Mock underlying price to 100
            self.builder.contractUtils.getUnderlyingLastPrice = MagicMock(return_value=100.0)
            
            result = self.builder.getATM(self.contracts)
            expect(result).to(have_length(2))  # Should return both put and call
            expect(result[0].Strike).to(equal(100.0))

        with it('filters by option type'):
            result = self.builder.getATM(self.contracts, type="call")
            expect(result).to(have_length(1))
            expect(result[0].Strike).to(equal(100.0))

        with it('returns empty list when no contracts'):
            result = self.builder.getATM([])
            expect(result).to(have_length(0))

    with context('getDeltaContract'):
        with before.each:
            # Create mock contracts with different deltas
            self.delta_contracts = []
            for strike, delta in [(95, 0.7), (100, 0.5), (105, 0.2)]:
                contract = OptionContract()
                contract._strike = strike
                contract._right = OptionRight.Call
                
                # Set both greeks and BSMGreeks
                contract._greeks.delta = delta
                
                # Create BSMGreeks mock directly on the instance
                bsm_greeks = MagicMock()
                bsm_greeks.configure_mock(Delta=delta)  # Use configure_mock for consistent property behavior
                contract._bsm_greeks = bsm_greeks
                
                self.delta_contracts.append(contract)
                
            # Sort contracts by strike
            self.delta_contracts.sort(key=lambda x: x.Strike)
            
            # Mock BSM setGreeks to do nothing since we've already set up the Greeks
            self.builder.bsm.setGreeks = MagicMock()
            
            # Mock isITM for delta filtering
            self.builder.bsm.isITM = MagicMock(return_value=True)

        with it('returns contract with closest delta'):
            result = self.builder.getDeltaContract(self.delta_contracts, delta=30)  # 0.3 delta
            expect(abs(result.BSMGreeks.Delta)).to(equal(0.2))

        with it('returns None when no delta specified'):
            result = self.builder.getDeltaContract(self.delta_contracts)
            expect(result).to(be_none)

        with it('handles empty contract list'):
            result = self.builder.getDeltaContract([])
            expect(result).to(be_none)

        with it('handles out of range delta values'):
            # Test delta higher than available
            result = self.builder.getDeltaContract(self.delta_contracts, delta=80)  # 0.8 delta
            expect(abs(result.BSMGreeks.Delta)).to(equal(0.7))
            
            # Test delta lower than available
            result = self.builder.getDeltaContract(self.delta_contracts, delta=10)  # 0.1 delta
            expect(abs(result.BSMGreeks.Delta)).to(equal(0.2))

    with context('getSpread'):
        with before.each:
            # Create mock contracts for spread testing
            self.spread_contracts = []
            for strike in [95, 100, 105]:
                contract = OptionContract()
                contract._strike = strike
                contract._right = OptionRight.Call
                self.spread_contracts.append(contract)

        with it('creates call spread correctly'):
            result = self.builder.getSpread(
                self.spread_contracts,
                type="call",
                strike=100,
                wingSize=5
            )
            expect(result).to(have_length(2))
            expect(result[0].Strike).to(equal(100.0))
            expect(result[1].Strike).to(equal(105.0))

        with it('creates put spread correctly'):
            # Change contracts to puts
            for contract in self.spread_contracts:
                contract._right = OptionRight.Put
                
            result = self.builder.getSpread(
                self.spread_contracts,
                type="put",
                strike=100,
                wingSize=5
            )
            expect(result).to(have_length(2))
            expect(result[0].Strike).to(equal(100.0))
            expect(result[1].Strike).to(equal(95.0))

        with it('returns empty list when invalid type'):
            result = self.builder.getSpread(
                self.spread_contracts,
                type="invalid",
                strike=100
            )
            expect(result).to(be_none)

    with context('getWing'):
        with it('returns correct wing contract'):
            # Create contracts with different strikes
            wing_contract = OptionContract()
            wing_contract._strike = 105.0
            far_contract = OptionContract()
            far_contract._strike = 110.0
            
            contracts = [
                self.mock_contract,  # Strike 100
                wing_contract,       # Wing at 5 points
                far_contract        # Too far
            ]
            
            result = self.builder.getWing(contracts, wingSize=5)
            expect(result.Strike).to(equal(105.0))

        with it('returns None when wing size not specified'):
            result = self.builder.getWing([self.mock_contract], wingSize=None)
            expect(result).to(be_none)

        with it('returns None when not enough contracts'):
            result = self.builder.getWing([self.mock_contract], wingSize=5)
            expect(result).to(be_none)

    with context('getContracts'):
        with before.each:
            # Create mock contracts with different strikes and prices
            self.filter_contracts = []
            for strike, price in [(95, 0.8), (100, 1.0), (105, 1.2)]:
                contract = OptionContract()
                contract._strike = strike
                contract._right = OptionRight.Call
                contract._bid_price = price - 0.05
                contract._ask_price = price + 0.05
                self.filter_contracts.append(contract)
                
            # Mock mid price for each contract with specific values
            def mock_mid_price(contract):
                if contract.Strike == 95:
                    return 0.8
                elif contract.Strike == 100:
                    return 1.0
                elif contract.Strike == 105:
                    return 1.2
                return 1.0
                
            self.builder.contractUtils.midPrice = MagicMock(side_effect=mock_mid_price)

        with it('filters by price range'):
            result = self.builder.getContracts(
                self.filter_contracts,
                fromPrice=0.9,
                toPrice=1.1
            )
            expect(result).to(have_length(1))  # Should only return the contract with price 1.0
            expect(result[0].Strike).to(equal(100.0))

        with it('filters by strike range'):
            result = self.builder.getContracts(
                self.filter_contracts,
                fromStrike=98,
                toStrike=102
            )
            expect(result).to(have_length(1))
            expect(result[0].Strike).to(equal(100.0))

        with it('handles reverse sorting'):
            result = self.builder.getContracts(
                self.filter_contracts,
                reverse=True
            )
            expect(result[0].Strike).to(equal(105.0))
            expect(result[-1].Strike).to(equal(95.0))

    with context('strike price filtering'):
        with before.each:
            # Create mock contracts with different deltas
            self.strike_contracts = []
            # For Calls: delta decreases as strike increases
            for strike, delta in [(95, 0.7), (100, 0.5), (105, 0.3)]:
                contract = OptionContract()
                contract._strike = strike
                contract._right = OptionRight.Call
                
                # Set both greeks and BSMGreeks
                contract._greeks.delta = delta
                
                # Create BSMGreeks mock directly on the instance
                bsm_greeks = MagicMock()
                bsm_greeks.configure_mock(Delta=delta)  # Use configure_mock for consistent property behavior
                contract._bsm_greeks = bsm_greeks
                
                self.strike_contracts.append(contract)
                
            # Sort contracts by strike in ascending order for Calls
            self.strike_contracts.sort(key=lambda x: x.Strike)
            
            # Mock BSM setGreeks to do nothing since we've already set up the Greeks
            self.builder.bsm.setGreeks = MagicMock()
            
            # Mock isITM for delta filtering - should return False for OTM options
            self.builder.bsm.isITM = MagicMock(side_effect=lambda x: x.Strike <= 100.0)

        with it('gets from delta strike correctly'):
            # For Call options:
            # Strike 95: delta 0.7 (above target 0.4)
            # Strike 100: delta 0.5 (above target 0.4)
            # Strike 105: delta 0.3 (below target 0.4)
            # getFromDeltaStrike returns first strike where delta >= target
            
            # Create a new list with just the contracts we need
            test_contracts = []
            for strike, delta in [(95, 0.7), (100, 0.5), (105, 0.3)]:
                contract = OptionContract()
                contract._strike = strike
                contract._right = OptionRight.Call
                
                # Set both greeks and BSMGreeks
                contract._greeks.delta = delta
                
                # Create BSMGreeks mock directly on the instance
                bsm_greeks = MagicMock()
                bsm_greeks.configure_mock(Delta=delta)  # Use configure_mock for consistent property behavior
                contract._bsm_greeks = bsm_greeks
                
                test_contracts.append(contract)
            
            # Sort contracts by strike in ascending order for Calls
            test_contracts.sort(key=lambda x: x.Strike)
            
            # Mock isITM to return True for all contracts to ensure they're considered
            self.builder.bsm.isITM = MagicMock(return_value=True)
            
            result = self.builder.getFromDeltaStrike(
                test_contracts,
                delta=40  # 0.4 delta
            )
            # For Calls: getFromDeltaStrike returns first strike where delta >= target
            # Strike 100 has delta 0.5 which is >= 0.4
            expect(result).to(equal(100.0))  # First strike with delta >= 0.4

        with it('gets to delta strike correctly'):
            result = self.builder.getToDeltaStrike(
                self.strike_contracts,
                delta=40  # 0.4 delta
            )
            expect(abs(result - 100.0)).to(be_below(0.02))  # Allow for small offset

        with it('returns default values when no contracts match'):
            result = self.builder.getFromDeltaStrike(
                [],
                delta=40,
                default=float('inf')
            )
            expect(result).to(equal(float('inf')))

    with context('spread creation edge cases'):
        with it('handles empty contract list'):
            result = self.builder.getSpread([], type="call", strike=100)
            expect(result).to(have_length(0))

        with it('respects price constraints'):
            # Create mock contracts with different prices
            contract2 = OptionContract()
            contract2._strike = 105.0
            contract2._right = OptionRight.Call
            contract2._bid_price = 1.95
            contract2._ask_price = 2.05
            
            contracts = [
                self.mock_contract,  # mid price 1.0
                contract2            # mid price will be different
            ]
            
            # Mock different mid prices for spread legs
            def mock_mid_price(contract):
                if contract.Strike == 100.0:
                    return 1.0
                elif contract.Strike == 105.0:
                    return 2.0
                return 1.0
                
            self.builder.contractUtils.midPrice = MagicMock(side_effect=mock_mid_price)
            
            # Mock security to always be tradable
            self.builder.contractUtils.getSecurity = MagicMock(
                return_value=MagicMock(IsTradable=True)
            )
            
            # Test with tight price constraints
            result = self.builder.getSpread(
                contracts,
                type="call",
                wingSize=10,
                fromPrice=0.0,  # Minimum net premium
                toPrice=0.5     # Maximum net premium - less than spread width (2.0 - 1.0 = 1.0)
            )
            expect(result).to(have_length(0))  # Should be empty as spread price > toPrice
            
            # Test with wider constraints
            result = self.builder.getSpread(
                contracts,
                type="call",
                wingSize=10,
                fromPrice=0.0,
                toPrice=2.0     # Now allow higher premiums
            )
            expect(result).to(have_length(2))  # Should return spread as price is within range

        with it('handles premium order correctly'):
            # Create mock contracts with different strikes
            contract2 = OptionContract()
            contract2._strike = 105.0
            contract2._right = OptionRight.Call
            contract2._bid_price = 1.45
            contract2._ask_price = 1.55
            
            contract3 = OptionContract()
            contract3._strike = 110.0
            contract3._right = OptionRight.Call
            contract3._bid_price = 0.95
            contract3._ask_price = 1.05
            
            contracts = [
                self.mock_contract,  # Strike 100
                contract2,           # Strike 105
                contract3            # Strike 110
            ]
            
            # Mock mid prices for spread calculation
            def mock_mid_price(contract):
                if contract.Strike == 100.0:
                    return 1.0
                elif contract.Strike == 105.0:
                    return 1.5
                else:
                    return 1.0
                    
            self.builder.contractUtils.midPrice = MagicMock(side_effect=mock_mid_price)
            
            # Mock security to always be tradable
            self.builder.contractUtils.getSecurity = MagicMock(
                return_value=MagicMock(IsTradable=True)
            )
            
            # Test max premium order
            result = self.builder.getSpread(
                contracts,
                type="call",
                wingSize=10,  # Allow wider spreads
                premiumOrder='max',
                fromPrice=0.0,  # Add price range
                toPrice=2.0
            )
            expect(result).to(have_length(2))
            # For max premium, expect the spread with largest price difference
            expect(result[0].Strike).to(equal(105.0))  # Higher premium leg
            expect(result[1].Strike).to(equal(110.0))  # Lower premium leg
            
            # Test min premium order
            result = self.builder.getSpread(
                contracts,
                type="call",
                wingSize=10,  # Allow wider spreads
                premiumOrder='min',
                fromPrice=0.0,  # Add price range
                toPrice=2.0
            )
            expect(result).to(have_length(2))
            # For min premium, expect the spread with smallest price difference
            expect(result[0].Strike).to(equal(100.0))  # Lower premium leg
            expect(result[1].Strike).to(equal(110.0))  # Higher premium leg