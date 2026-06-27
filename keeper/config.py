"""
config.py — loads environment, holds contract addresses, ABIs, and web3 instances.

After deployment:
  1. Fill .env with real addresses and keys
  2. Set WHITELISTED_PAIRS in .env with the pairs you want to track
  3. Paste ABI arrays from Basescan into the ABI constants below
  4. Run main.py
"""

import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

# ============================================================
# Environment
# ============================================================

KEEPER_PRIVATE_KEY      = os.environ["KEEPER_PRIVATE_KEY"]
ALCHEMY_HTTP_URL        = os.environ["ALCHEMY_HTTP_URL"]
ALCHEMY_WSS_URL         = os.environ["ALCHEMY_WSS_URL"]

HOOK_CONTRACT           = Web3.to_checksum_address(os.environ["HOOK_CONTRACT"])
VAULT                   = Web3.to_checksum_address(os.environ["VAULT"])
ASSET_MANAGER           = Web3.to_checksum_address(os.environ["ASSET_MANAGER"])
STRATEGY_MANAGER        = Web3.to_checksum_address(os.environ["STRATEGY_MANAGER"])

RANGE_WIDTH_BPS         = int(os.environ.get("RANGE_WIDTH_BPS", 1000))
UPDATE_INTERVAL_SECONDS = int(os.environ.get("UPDATE_INTERVAL_SECONDS", 3600))
DEADLINE_BUFFER_SECONDS = int(os.environ.get("DEADLINE_BUFFER_SECONDS", 120))

# ============================================================
# Migration filters — all must pass before migration is allowed
# ============================================================

# Minimum 24h volume in USD a candidate must sustain
MIN_DAILY_VOLUME_USD    = float(os.environ.get("MIN_DAILY_VOLUME_USD", 50_000))

# Minimum TVL in USD
MIN_LIQUIDITY_USD       = float(os.environ.get("MIN_LIQUIDITY_USD", 100_000))

# Minimum volume/TVL ratio (e.g. 0.3 = 30% daily turnover)
MIN_VOLUME_TVL_RATIO    = float(os.environ.get("MIN_VOLUME_TVL_RATIO", 0.3))

# Minimum pool age in days before it can be considered
MIN_POOL_AGE_DAYS       = int(os.environ.get("MIN_POOL_AGE_DAYS", 90))

# How many consecutive hourly readings must pass filters before migration
# Prevents reacting to one-off volume spikes like the RNBW $200k→$19k case
MIN_CONSECUTIVE_GOOD_READINGS = int(os.environ.get("MIN_CONSECUTIVE_GOOD_READINGS", 3))

# ============================================================
# Whitelisted pairs
# You control exactly which pairs the system can ever LP into.
# Format: baseToken:quoteToken:fee:tickSpacing:poolAddress
# poolAddress is the actual Uniswap v4 pool — fill after deployment.
#
# Example:
# WHITELISTED_PAIRS=0xNOCK:0xUSDC:10000:200:0xPOOL1,0xRNBW:0xUSDC:10000:200:0xPOOL2
# ============================================================

WHITELISTED_PAIRS_RAW = os.environ.get("WHITELISTED_PAIRS", "")
WHITELISTED_PAIRS: list[dict] = []

for entry in WHITELISTED_PAIRS_RAW.split(","):
    entry = entry.strip()
    if not entry:
        continue
    parts = entry.split(":")
    if len(parts) < 5:
        raise ValueError(
            f"Invalid WHITELISTED_PAIRS entry: '{entry}'. "
            "Expected format: baseToken:quoteToken:fee:tickSpacing:poolAddress"
        )
    WHITELISTED_PAIRS.append({
        "base_token":   Web3.to_checksum_address(parts[0]),
        "quote_token":  Web3.to_checksum_address(parts[1]),
        "fee":          int(parts[2]),
        "tick_spacing": int(parts[3]),
        "pool_address": Web3.to_checksum_address(parts[4]),
    })

# ============================================================
# Web3
# ============================================================

w3 = Web3(Web3.HTTPProvider(ALCHEMY_HTTP_URL))
assert w3.is_connected(), "Web3 HTTP connection failed — check ALCHEMY_HTTP_URL"

KEEPER_ACCOUNT = w3.eth.account.from_key(KEEPER_PRIVATE_KEY)
KEEPER_ADDRESS = KEEPER_ACCOUNT.address

# ============================================================
# ABIs — paste from Basescan after deployment and verification
# ============================================================

# HookContract ABI — paste full ABI from Basescan
HOOK_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "oldCenter", "type": "int24"},
            {"indexed": False, "name": "newCenter", "type": "int24"},
            {"indexed": False, "name": "drift",     "type": "int24"},
            {"indexed": False, "name": "timestamp", "type": "uint256"},
        ],
        "name": "RangeRepositionFlagged",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "name": "amount0",  "type": "uint256"},
            {"indexed": False, "name": "amount1",  "type": "uint256"},
            {"indexed": False, "name": "driftBps", "type": "uint256"},
        ],
        "name": "RatioRebalanceFlagged",
        "type": "event",
    },
]

# StrategyManager ABI — paste full ABI from Basescan
STRATEGY_MANAGER_ABI = [
    {
        "inputs": [
            {"name": "targetToken", "type": "address"},
            {"name": "fee",         "type": "uint24"},
            {"name": "tickSpacing", "type": "int24"},
        ],
        "name": "registerCandidate",
        "outputs": [{"name": "id", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "id",                 "type": "bytes32"},
            {"name": "dailyVolumeUsd",     "type": "uint256"},
            {"name": "liquidityUsd",       "type": "uint256"},
            {"name": "ourRoutedVolumeUsd", "type": "uint256"},
        ],
        "name": "updatePoolData",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "exitDeadline", "type": "uint256"},
        ],
        "name": "evaluateAndMigrate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "startingSqrtPriceX96",    "type": "uint160"},
            {"name": "tickLower",               "type": "int24"},
            {"name": "tickUpper",               "type": "int24"},
            {"name": "poolNeedsInitialization", "type": "bool"},
            {"name": "deadline",                "type": "uint256"},
        ],
        "name": "deployActiveCandidate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getActiveCandidate",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# ============================================================
# Contract instances
# ============================================================

hook_contract    = w3.eth.contract(address=HOOK_CONTRACT,    abi=HOOK_ABI)
strategy_manager = w3.eth.contract(address=STRATEGY_MANAGER, abi=STRATEGY_MANAGER_ABI)