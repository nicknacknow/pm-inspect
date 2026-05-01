"""Polymarket ABI definitions for transaction decoding."""

# V2 Order struct: (salt, maker, signer, tokenId, makerAmount, takerAmount, side, signatureType, timestamp, metadata, builder, signature)
# Removed vs V1: taker, expiration, nonce, feeRateBps
# Added vs V1:   timestamp, metadata, builder
# conditionId is also a new first param on matchOrders itself (not part of the order tuple)
ORDER_TUPLE_TYPE = "(uint256,address,address,uint256,uint256,uint256,uint8,uint8,uint256,bytes32,bytes32,bytes)"

# V2 matchOrders selector
# matchOrders(bytes32 conditionId, Order takerOrder, Order[] makerOrders,
#             uint256 takerFillAmount, uint256[] makerFillAmounts,
#             uint256 takerFeeAmount, uint256[] makerFeeAmounts)
# keccak256 of the canonical signature → 3c2b4399
# MethodID: 0x3c2b4399
MATCH_ORDERS_SELECTOR = bytes.fromhex("3c2b4399")

# ABI types for matchOrders (7 params)
# Note: conditionId (bytes32) is a new leading param in V2; takerReceiveAmount removed
MATCH_ORDERS_ABI_TYPES = [
    "bytes32",                  # conditionId (new in V2)
    ORDER_TUPLE_TYPE,           # takerOrder
    f"{ORDER_TUPLE_TYPE}[]",    # makerOrders array
    "uint256",                  # takerFillAmount
    "uint256[]",                # makerFillAmounts
    "uint256",                  # takerFeeAmount
    "uint256[]",                # makerFeeAmounts
]

# Both CTF and NegRisk exchanges use the same selector in V2
CTF_MATCH_ORDERS_SELECTOR = MATCH_ORDERS_SELECTOR
NEGRISK_MATCH_ORDERS_SELECTOR = MATCH_ORDERS_SELECTOR