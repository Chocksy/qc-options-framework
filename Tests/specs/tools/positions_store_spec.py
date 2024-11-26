from mamba import description, context, it, before
from expects import expect, equal, be_none, be_true, have_length, contain, have_key, raise_error
from datetime import datetime, date
import json
from unittest.mock import MagicMock

from Tools.PositionsStore import PositionsStore, PositionEncoder, PositionDecoder
from Tests.mocks.algorithm_imports import Symbol, OptionContract
from Tests.mocks.tools_mocks import MockContext, MockObjectStore
from Strategy.Position import Position, Leg, OrderType, WorkingOrder

with description('PositionsStore') as self:
    with before.each:
        self.context = MockContext()
        self.context.logger = MagicMock(
            error=MagicMock(),
            warning=MagicMock(),
            debug=MagicMock()
        )
        self.object_store = MockObjectStore()
        self.context.object_store = self.object_store
        self.store = PositionsStore(self.context)

    with context('store_positions'):
        with it('stores positions in JSON format'):
            # Create a test position
            open_order = OrderType(
                premium=100.0,
                fills=1,
                filled=True,
                fillPrice=100.0
            )
            close_order = OrderType(
                premium=0.0,
                fills=0,
                filled=False
            )
            position = Position(
                orderId="1",
                orderTag="TEST_1",
                strategy=None,
                strategyTag="TEST",
                strategyId="TEST_STRATEGY",
                expiryStr="20240101",
                expiry=datetime(2024, 1, 1),
                legs=[],
                contractSide={},
                openOrder=open_order,
                closeOrder=close_order
            )
            self.context.allPositions = {1: position}
            
            # Call store_positions
            self.store.store_positions()
            
            # Verify JSON was saved
            expect(self.object_store.saved_data).to(have_key("positions.json"))
            saved_json = json.loads(self.object_store.saved_data["positions.json"])
            expect(saved_json).to(have_key("1"))
            saved_position = saved_json["1"]
            expect(saved_position["orderId"]).to(equal("1"))
            expect(saved_position["orderTag"]).to(equal("TEST_1"))
            expect(saved_position["expiry"]).to(have_key("__datetime__"))
            expect(saved_position["expiry"]["__datetime__"]).to(equal("2024-01-01T00:00:00"))

        with it('handles empty positions dictionary'):
            self.context.allPositions = {}
            self.store.store_positions()
            expect(self.object_store.saved_data).to(have_key("positions.json"))
            saved_json = json.loads(self.object_store.saved_data["positions.json"])
            expect(saved_json).to(equal({}))

        with it('stores positions with legs'):
            # Create a test position with legs
            open_order = OrderType(
                premium=100.0,
                fills=1,
                filled=True,
                fillPrice=100.0
            )
            close_order = OrderType(
                premium=0.0,
                fills=0,
                filled=False
            )
            
            # Create legs
            leg1 = Leg(
                key="LEG1",
                expiry=datetime(2024, 1, 1),
                contractSide=1,
                symbol="AAPL",
                quantity=1,
                strike=150.0
            )
            leg2 = Leg(
                key="LEG2",
                expiry=datetime(2024, 1, 1),
                contractSide=-1,
                symbol="AAPL",
                quantity=-1,
                strike=160.0
            )
            
            position = Position(
                orderId="1",
                orderTag="TEST_1",
                strategy=None,
                strategyTag="TEST",
                strategyId="TEST_STRATEGY",
                expiryStr="20240101",
                expiry=datetime(2024, 1, 1),
                legs=[leg1, leg2],
                contractSide={},
                openOrder=open_order,
                closeOrder=close_order
            )
            self.context.allPositions = {1: position}
            
            # Call store_positions
            self.store.store_positions()
            
            # Verify JSON was saved
            expect(self.object_store.saved_data).to(have_key("positions.json"))
            saved_json = json.loads(self.object_store.saved_data["positions.json"])
            expect(saved_json).to(have_key("1"))
            saved_position = saved_json["1"]
            expect(saved_position["legs"]).to(have_length(2))
            expect(saved_position["legs"][0]["__dataclass__"]).to(equal("Leg"))
            expect(saved_position["legs"][0]["data"]["key"]).to(equal("LEG1"))
            expect(saved_position["legs"][1]["data"]["key"]).to(equal("LEG2"))
            
    with context('load_positions'):
        with it('loads positions from JSON format'):
            # Create a test position JSON
            open_order = OrderType(
                premium=100.0,
                fills=1,
                filled=True,
                fillPrice=100.0
            )
            close_order = OrderType(
                premium=0.0,
                fills=0,
                filled=False
            )
            position = Position(
                orderId="1",
                orderTag="TEST_1",
                strategy=None,
                strategyTag="TEST",
                strategyId="TEST_STRATEGY",
                expiryStr="20240101",
                expiry=datetime(2024, 1, 1),
                legs=[],
                contractSide={},
                openOrder=open_order,
                closeOrder=close_order
            )
            
            # Store the position data
            self.context.allPositions = {1: position}
            self.store.store_positions()
            stored_json = self.object_store.saved_data["positions.json"]
            self.object_store.stored_data["positions.json"] = stored_json
            
            # Reset context positions
            self.context.allPositions = {}
            
            # Call load_positions
            self.store.load_positions()
            
            # Verify positions were loaded
            expect(self.context.allPositions).to(have_length(1))
            expect(self.context.allPositions).to(have_key(1))
            loaded_position = self.context.allPositions[1]
            expect(loaded_position.orderId).to(equal("1"))
            expect(loaded_position.orderTag).to(equal("TEST_1"))
            expect(loaded_position.expiry).to(equal(datetime(2024, 1, 1)))

        with it('handles missing positions file'):
            self.store.load_positions()
            expect(self.context.allPositions).to(equal({}))

        with it('handles invalid JSON data'):
            self.object_store.stored_data["positions.json"] = "invalid json"
            self.store.load_positions()
            expect(self.context.allPositions).to(equal({}))

        with it('adds future positions to openPositions'):
            # Create a test position with future expiry
            open_order = OrderType(
                premium=100.0,
                fills=1,
                filled=True,
                fillPrice=100.0
            )
            close_order = OrderType(
                premium=0.0,
                fills=0,
                filled=False
            )
            future_date = datetime(2099, 1, 1)  # Far future date
            position = Position(
                orderId="1",
                orderTag="TEST_1",
                strategy=None,
                strategyTag="TEST",
                strategyId="TEST_STRATEGY",
                expiryStr="20990101",
                expiry=future_date,
                legs=[],
                contractSide={},
                openOrder=open_order,
                closeOrder=close_order
            )
            
            # Store and load the position
            self.context.allPositions = {1: position}
            self.store.store_positions()
            stored_json = self.object_store.saved_data["positions.json"]
            self.object_store.stored_data["positions.json"] = stored_json
            
            # Reset context positions
            self.context.allPositions = {}
            self.context.openPositions = {}
            
            # Call load_positions
            self.store.load_positions()
            
            # Verify position was added to openPositions
            expect(self.context.openPositions).to(have_key("TEST_1"))
            expect(self.context.openPositions["TEST_1"]).to(equal("1"))

        with it('loads positions with legs'):
            # Create a test position with legs
            open_order = OrderType(
                premium=100.0,
                fills=1,
                filled=True,
                fillPrice=100.0
            )
            close_order = OrderType(
                premium=0.0,
                fills=0,
                filled=False
            )
            
            # Create legs
            leg1 = Leg(
                key="LEG1",
                expiry=datetime(2024, 1, 1),
                contractSide=1,
                symbol="AAPL",
                quantity=1,
                strike=150.0
            )
            leg2 = Leg(
                key="LEG2",
                expiry=datetime(2024, 1, 1),
                contractSide=-1,
                symbol="AAPL",
                quantity=-1,
                strike=160.0
            )
            
            position = Position(
                orderId="1",
                orderTag="TEST_1",
                strategy=None,
                strategyTag="TEST",
                strategyId="TEST_STRATEGY",
                expiryStr="20240101",
                expiry=datetime(2024, 1, 1),
                legs=[leg1, leg2],
                contractSide={},
                openOrder=open_order,
                closeOrder=close_order
            )
            
            # Store and load the position
            self.context.allPositions = {1: position}
            self.store.store_positions()
            stored_json = self.object_store.saved_data["positions.json"]
            self.object_store.stored_data["positions.json"] = stored_json
            
            # Reset context positions
            self.context.allPositions = {}
            
            # Call load_positions
            self.store.load_positions()
            
            # Verify positions were loaded with legs
            expect(self.context.allPositions).to(have_length(1))
            loaded_position = self.context.allPositions[1]
            expect(loaded_position.legs).to(have_length(2))
            expect(loaded_position.legs[0].key).to(equal("LEG1"))
            expect(loaded_position.legs[0].contractSide).to(equal(1))
            expect(loaded_position.legs[1].key).to(equal("LEG2"))
            expect(loaded_position.legs[1].contractSide).to(equal(-1))