# region imports
from AlgorithmImports import *
# endregion
import json
import pickle
import importlib
from dataclasses import asdict, is_dataclass, fields
from datetime import datetime, date, time
from Strategy.Position import Position, Leg, OrderType, Order, WorkingOrder

class PositionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Position):
            return self.serialize_position(obj)
        elif isinstance(obj, (Leg, OrderType, WorkingOrder)):
            return self.serialize_dataclass(obj)
        elif isinstance(obj, (datetime, date, time)):
            return {
                "__datetime__": obj.isoformat()
            }
        elif isinstance(obj, Symbol):
            return {
                "__symbol__": str(obj)
            }
        elif isinstance(obj, OptionContract):
            return {
                "__optioncontract__": {
                    "symbol": str(obj.Symbol),
                    "right": obj.Right,
                    "strike": obj.Strike,
                    "expiry": obj# region imports
from AlgorithmImports import *
# endregion
import json
import pickle
import importlib
from dataclasses import asdict, is_dataclass, fields
from datetime import datetime, date, time
from Strategy.Position import Position, Leg, OrderType, Order, WorkingOrder

class PositionEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Position):
            return self.serialize_position(obj)
        elif isinstance(obj, (Leg, OrderType, WorkingOrder)):
            return self.serialize_dataclass(obj)
        elif isinstance(obj, (datetime, date, time)):
            return {
                "__datetime__": obj.isoformat()
            }
        elif isinstance(obj, Symbol):
            return {
                "__symbol__": str(obj)
            }
        elif isinstance(obj, OptionContract):
            return {
                "__optioncontract__": {
                    "symbol": str(obj.Symbol),
                    "right": obj.Right,
                    "strike": obj.Strike,
                    "expiry": obj.Expiry.isoformat()
                }
            }
        elif isinstance(obj, float) and math.isnan(obj):
            return {"__nan__": True}
        return super().default(obj)

    def serialize_position(self, position):
        serialized = {}
        for field in position.__dataclass_fields__:
            value = getattr(position, field)
            if field == 'strategy':
                # Serialize strategy as class name
                serialized[field] = {
                    "__strategy__": value.__class__.__name__
                }
            elif isinstance(value, (Leg, OrderType, WorkingOrder)):
                serialized[field] = self.serialize_dataclass(value)
            elif isinstance(value, list) and value and isinstance(value[0], Leg):
                serialized[field] = [self.serialize_dataclass(leg) for leg in value]
            elif isinstance(value, dict) and value and isinstance(next(iter(value.values())), int):
                # Handle contractSide dictionary
                serialized[field] = {str(k): v for k, v in value.items()}
            else:
                serialized[field] = value
        return serialized

    def serialize_dataclass(self, obj):
        return {
            "__dataclass__": obj.__class__.__name__,
            "data": {f: getattr(obj, f) for f in obj.__dataclass_fields__ if self.is_serializable(getattr(obj, f))}
        }

    def is_serializable(self, obj):
        try:
            json.dumps(obj)
            return True
        except (TypeError, OverflowError):
            return False

class PositionDecoder(json.JSONDecoder):
    def __init__(self, context, *args, **kwargs):
        self.context = context
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, dct):
        if "__dataclass__" in dct:
            cls_name = dct["__dataclass__"]
            if cls_name == "Position":
                return self.reconstruct_position(dct["data"])
            elif cls_name == "Leg":
                return Leg(**dct["data"])
            elif cls_name == "OrderType":
                return OrderType(**dct["data"])
            elif cls_name == "WorkingOrder":
                return WorkingOrder(**dct["data"])
        elif "__datetime__" in dct:
            return datetime.fromisoformat(dct["__datetime__"])
        elif "__symbol__" in dct:
            return Symbol.Create(dct["__symbol__"])
        elif "__optioncontract__" in dct:
            data = dct["__optioncontract__"]
            return OptionContract(
                Symbol.Create(data["symbol"]),
                data["right"],
                data["strike"],
                datetime.fromisoformat(data["expiry"])
            )
        elif "__strategy__" in dct:
            try:
                strategy_name = dct["__strategy__"]
                strategy_module = importlib.import_module(f'Alpha.{strategy_name}')
                strategy_class = getattr(strategy_module, strategy_name)
                return strategy_class(self.context)
            except Exception as e:
                self.context.logger.error(f"PositionStore: Alpha strategy_name: " {e}").Expiry.isoformat()
                return float('nan')

        elif "__nan__" in dct:
            return float('nan')
        return dct

    def reconstruct_position(self, data):
        if 'strategy' in data and isinstance(data['strategy'], dict) and "__strategy__" in data['strategy']:
            try:
                strategy_name = data['strategy']["__strategy__"]
                strategy_module = importlib.import_module(f'Alpha.{strategy_name}')
                strategy_class = getattr(strategy_module, strategy_name)
                data['strategy'] = strategy_class(self.context)
            except Exception as e:
                self.context.logger.error(f"PositionStore: Alpha strategy_name: " {e}").Expiry.isoformat()
            
        # Get the fields of the Position class that are part of __init__
        position_fields = {f.name for f in fields(Position) if f.init}

        # Filter the data to only include fields that are part of __init__
        filtered_data = {}
        for k, v in data.items():
            if k in position_fields:
                filtered_data[k] = v
            elif k not in fields(Position):
                self.context.logger.warning(f"Ignoring field '{k}' when reconstructing Position object. This field is not in the current Position class definition.")

        # Create the Position object
        position = Position(**filtered_data)

        
        
        # Set fields that are not part of __init__ manually
        for k, v in data.items():
            if k in fields(Position) and k not in filtered_data:
                setattr(position, k, v)

        return position

    def decode(self, json_string):
        data = super().decode(json_string)
        if isinstance(data, dict) and all(isinstance(key, str) for key in data.keys()):
            return {int(k): self.reconstruct_position(v) for k, v in data.items()}
        return data


class PositionsStore:
    def __init__(self, context):
        self.context = context

    def store_positions(self):
        positions = self.context.allPositions
        json_data = json.dumps(positions, cls=PositionEncoder, indent=2)
        self.context.object_store.save("positions.json", json_data)

    def load_positions(self):
        try:
            json_data = self.context.object_store.read("positions.json")
            decoder = PositionDecoder(self.context)
            unpacked_positions = decoder.decode(json_data)
            self.context.allPositions = unpacked_positions

            # Add positions with future expiry and not closed to openPositions
            for position in unpacked_positions.values():
                if position.expiry and position.expiry.date() > self.context.Time.date() and not position.closeOrder.filled:
                    self.context.openPositions[position.orderTag] = position.orderId
        except Exception as e:
            self.context.logger.error(f"Error reading or deserializing JSON data: {e}").Expiry.isoformat()
                }
            }
        elif isinstance(obj, float) and math.isnan(obj):
            return {"__nan__": True}
        return super().default(obj)

    def serialize_position(self, position):
        serialized = {}
        for field in position.__dataclass_fields__:
            value = getattr(position, field)
            if field == 'strategy':
                # Serialize strategy as class name
                serialized[field] = {
                    "__strategy__": value.__class__.__name__
                }
            elif isinstance(value, (Leg, OrderType, WorkingOrder)):
                serialized[field] = self.serialize_dataclass(value)
            elif isinstance(value, list) and value and isinstance(value[0], Leg):
                serialized[field] = [self.serialize_dataclass(leg) for leg in value]
            elif isinstance(value, dict) and value and isinstance(next(iter(value.values())), int):
                # Handle contractSide dictionary
                serialized[field] = {str(k): v for k, v in value.items()}
            else:
                serialized[field] = value
        return serialized

    def serialize_dataclass(self, obj):
        return {
            "__dataclass__": obj.__class__.__name__,
            "data": {f: getattr(obj, f) for f in obj.__dataclass_fields__ if self.is_serializable(getattr(obj, f))}
        }

    def is_serializable(self, obj):
        try:
            json.dumps(obj)
            return True
        except (TypeError, OverflowError):
            return False

class PositionDecoder(json.JSONDecoder):
    def __init__(self, context, *args, **kwargs):
        self.context = context
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, dct):
        if "__dataclass__" in dct:
            cls_name = dct["__dataclass__"]
            if cls_name == "Position":
                return self.reconstruct_position(dct["data"])
            elif cls_name == "Leg":
                return Leg(**dct["data"])
            elif cls_name == "OrderType":
                return OrderType(**dct["data"])
            elif cls_name == "WorkingOrder":
                return WorkingOrder(**dct["data"])
        elif "__datetime__" in dct:
            return datetime.fromisoformat(dct["__datetime__"])
        elif "__symbol__" in dct:
            return Symbol.Create(dct["__symbol__"])
        elif "__optioncontract__" in dct:
            data = dct["__optioncontract__"]
            return OptionContract(
                Symbol.Create(data["symbol"]),
                data["right"],
                data["strike"],
                datetime.fromisoformat(data["expiry"])
            )
        elif "__strategy__" in dct:
            strategy_name = dct["__strategy__"]
            strategy_module = importlib.import_module(f'Alpha.{strategy_name}')
            strategy_class = getattr(strategy_module, strategy_name)
            return strategy_class(self.context)
        elif "__nan__" in dct:
            return float('nan')
        return dct

    def reconstruct_position(self, data):
        if 'strategy' in data and isinstance(data['strategy'], dict) and "__strategy__" in data['strategy']:
            strategy_name = data['strategy']["__strategy__"]
            strategy_module = importlib.import_module(f'Alpha.{strategy_name}')
            strategy_class = getattr(strategy_module, strategy_name)
            data['strategy'] = strategy_class(self.context)

        # Get the fields of the Position class that are part of __init__
        position_fields = {f.name for f in fields(Position) if f.init}

        # Filter the data to only include fields that are part of __init__
        filtered_data = {}
        for k, v in data.items():
            if k in position_fields:
                filtered_data[k] = v
            elif k not in fields(Position):
                self.context.logger.warning(f"Ignoring field '{k}' when reconstructing Position object. This field is not in the current Position class definition.")

        # Create the Position object
        position = Position(**filtered_data)

        # Set fields that are not part of __init__ manually
        for k, v in data.items():
            if k in fields(Position) and k not in filtered_data:
                setattr(position, k, v)

        return position

    def decode(self, json_string):
        data = super().decode(json_string)
        if isinstance(data, dict) and all(isinstance(key, str) for key in data.keys()):
            return {int(k): self.reconstruct_position(v) for k, v in data.items()}
        return data


class PositionsStore:
    def __init__(self, context):
        self.context = context

    def store_positions(self):
        positions = self.context.allPositions
        json_data = json.dumps(positions, cls=PositionEncoder, indent=2)
        self.context.object_store.save("positions.json", json_data)

    def load_positions(self):
        try:
            json_data = self.context.object_store.read("positions.json")
            decoder = PositionDecoder(self.context)
            unpacked_positions = decoder.decode(json_data)
            self.context.allPositions = unpacked_positions

            # Add positions with future expiry and not closed to openPositions
            for position in unpacked_positions.values():
                if position.expiry and position.expiry.date() > self.context.Time.date() and not position.closeOrder.filled:
                    self.context.openPositions[position.orderTag] = position.orderId
        except Exception as e:
            self.context.logger.error(f"Error reading or deserializing JSON data: {e}")