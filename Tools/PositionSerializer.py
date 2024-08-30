import pickle
import json

class PositionSerializer:

    def __init__(self, context):
        self.context = context

    @staticmethod
    def unpack_leg(leg):
        return {
            'key': leg.key,
            'expiry': leg.expiry.isoformat(),
            'contractSide': leg.contractSide,
            'symbol': str(leg.contract.symbol),  # Unpack symbol as string
            'quantity': leg.quantity,
            'strike': leg.strike
            # 'contract': leg.contract # QC object, can't be serialized
        }

    @staticmethod
    def unpack_order_type(order):
        return {
            'premium': order.premium,
            'fills': order.fills, 
            'limitOrderExpiryDttm': order.limitOrderExpiryDttm.isoformat() if order.limitOrderExpiryDttm else None,
            'limitOrderPrice': order.limitOrderPrice,
            'transactionIds': order.transactionIds,
            'priceProgressList': order.priceProgressList,
        }

    @staticmethod
    def unpack_position(position):
        return {
            'orderId': position.orderId,
            'orderTag': position.orderTag,
            'strategyTag': position.strategyTag,
            'strategyId': position.strategyId,
            'expiryStr': position.expiryStr,
            'expiry': position.expiry.isoformat(),
            'orderQuantity': position.orderQuantity,
            'maxOrderQuantity': position.maxOrderQuantity,
            'targetProfit': position.targetProfit,
            'legs': [PositionSerializer.unpack_leg(leg) for leg in position.legs],
            'contractSide': {symbol.Value: side for symbol, side in position.contractSide.items()},
            'openOrder': PositionSerializer.unpack_order_type(position.openOrder),
            'closeOrder': PositionSerializer.unpack_order_type(position.closeOrder),
            'openDttm': position.openDttm.isoformat() if position.openDttm else None,
            'openDt': position.openDt,
            'openDTE': position.openDTE,
            'underlyingPriceAtOpen': position.underlyingPriceAtOpen,
            'positionPnL': position.positionPnL,
            'closeReason': position.closeReason,
            'PnL': position.PnL,
            'orderCancelled': position.orderCancelled,
            'filled': position.filled,
            'limitOrder': position.limitOrder,
            'priceProgressList': position.priceProgressList,
            # Add more fields if necessary
        }

    @staticmethod
    def serialize_positions(positions, object_store):
        # Unpack positions to serializable format
        unpacked_positions = {k: PositionSerializer.unpack_position(v) for k, v in positions.items()}
        
        # Convert the dictionary to a JSON string
        json_data = json.dumps(unpacked_positions, indent=4)
        
        # Save the JSON string as a file in the object store
        object_store.save("positions.json", json_data)
        
        # Pickle the unpacked dictionary
        pickle_data = pickle.dumps(unpacked_positions)
        
        # Save the pickled data as a binary file in the object store
        object_store.save_bytes("positions.pkl", pickle_data)

    
    def deserialize_positions(self):
        # Load the pickled data

        try:
            pickle_data = self.context.object_store.read_bytes("positions.pkl")
            unpacked_positions = pickle.loads(pickle_data)
        except:
            self.context.logger.debug("No position file from previous session found to load.")

       # Ensure that the positions are deserialized as a dictionary
        if isinstance(unpacked_positions, str):
            self.context.logger.debug("Unpacked positions is a string, attempting to load as JSON.")
            unpacked_positions = json.loads(unpacked_positions)
            self.context.logger.debug(f"Type of unpacked_positions after JSON load: {type(unpacked_positions)}")
        elif isinstance(unpacked_positions, dict):
            self.context.logger.debug("Unpacked positions is already a dictionary.")

        return unpacked_positions

    def get_option_symbols_from_positions(self):

        symbols_to_add = []

        unpacked_positions = self.deserialize_positions()

        if not unpacked_positions:
            return []

        # Debugging output to check the type before processing
        self.context.logger.debug(f"Processing unpacked_positions. Type: {type(unpacked_positions)}")

        # Check if unpacked_positions is actually a dictionary
        if not isinstance(unpacked_positions, dict):
            self.context.logger.debug(f"Error: Expected a dictionary but got {type(unpacked_positions)}")
            return
        
        # Iterate over the positions manually without .items()
        for position_id in unpacked_positions:
            position = unpacked_positions[position_id]
            
            # Check if position is a dictionary
            if not isinstance(position, dict):
                self.context.logger.debug(f"Error: Expected a dictionary for position {position_id} but got {type(position)}")
                continue

            self.context.logger.debug(f"Processing Position ID: {position_id}, Content: {position}")
            
            for leg in position.get('legs', []):
                self.context.logger.debug(f"Processing Leg: {leg}")

                leg_symbol = str(leg['symbol'])
            
            symbols_to_add.append(leg_symbol)

        return symbols_to_add