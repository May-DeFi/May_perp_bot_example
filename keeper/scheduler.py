"""
scheduler.py — hourly loop.

Every UPDATE_INTERVAL_SECONDS:
  1. Fetch volume + liquidity for all whitelisted pairs from GeckoTerminal
  2. Run migration filters — all must pass MIN_CONSECUTIVE_GOOD_READINGS times
  3. Call updatePoolData on StrategyManager for pairs that pass
  4. Call evaluateAndMigrate — contract decides whether to move
  5. If migration happened, call deployActiveCandidate with current price

Whitelist enforcement:
  The keeper will ONLY ever register and consider pairs listed in
  WHITELISTED_PAIRS. No autonomous discovery. You control the list.

Consecutive readings filter:
  A pair must pass ALL quality filters (volume, liquidity, age, volume/TVL)
  for MIN_CONSECUTIVE_GOOD_READINGS consecutive hourly checks before it
  can be registered as a migration candidate. Prevents reacting to spikes.
"""

import asyncio
import logging
from collections import defaultdict
from web3 import Web3

import config
from pool_data import fetch_pool_data, passes_migration_filters
from ticks import compute_tick_range, compute_sqrt_price_x96_from_price
from events import _send_tx, _deadline

log = logging.getLogger(__name__)

# Tracks how many consecutive passing readings each pair has accumulated.
# Keyed by pool_address. Resets to 0 on any failed reading.
_consecutive_good_readings: dict[str, int] = defaultdict(int)

# Tracks which pairs are already registered in StrategyManager
# so we don't re-register on every tick.
_registered_pairs: set[str] = set()


def _compute_candidate_id(base_token: str, fee: int, tick_spacing: int) -> bytes:
    """
    Mirrors StrategyManager.registerCandidate id computation:
    keccak256(abi.encode(targetToken, fee, tickSpacing))
    """
    return Web3.solidity_keccak(
        ["address", "uint24", "int24"],
        [Web3.to_checksum_address(base_token), fee, tick_spacing]
    )


async def _register_pair(pair: dict) -> None:
    """Register a single whitelisted pair in StrategyManager."""
    pool_address = pair["pool_address"]
    if pool_address in _registered_pairs:
        return

    log.info(
        f"Registering pair | baseToken={pair['base_token']} "
        f"fee={pair['fee']} tickSpacing={pair['tick_spacing']}"
    )
    await _send_tx(
        config.strategy_manager.functions.registerCandidate(
            pair["base_token"],
            pair["fee"],
            pair["tick_spacing"],
        )
    )
    _registered_pairs.add(pool_address)


async def update_pool_data() -> None:
    """
    Fetch data for all whitelisted pairs and apply consecutive readings filter.

    Only pairs that have accumulated MIN_CONSECUTIVE_GOOD_READINGS consecutive
    passing readings get registered and have their data pushed to the contract.
    Pairs that fail any filter have their counter reset to 0.
    """
    for pair in config.WHITELISTED_PAIRS:
        pool_address = pair["pool_address"]
        base_token   = pair["base_token"]

        data = await fetch_pool_data(pool_address)
        if not data:
            log.warning(f"No data for {base_token} — skipping, resetting counter")
            _consecutive_good_readings[pool_address] = 0
            continue

        passes, reason = passes_migration_filters(data, pair, config)

        if not passes:
            log.info(
                f"Pair {base_token} failed filter: {reason} — "
                f"resetting consecutive counter"
            )
            _consecutive_good_readings[pool_address] = 0
            continue

        # Passed this reading — increment counter
        _consecutive_good_readings[pool_address] += 1
        count = _consecutive_good_readings[pool_address]

        log.info(
            f"Pair {base_token} passed filters "
            f"({count}/{config.MIN_CONSECUTIVE_GOOD_READINGS} consecutive) | "
            f"volume=${data['volume_usd']:,.0f} "
            f"liquidity=${data['liquidity_usd']:,.0f} "
            f"age={data['pool_age_days']}d"
        )

        # Only push to contract once it has enough consecutive good readings
        if count < config.MIN_CONSECUTIVE_GOOD_READINGS:
            log.info(
                f"Waiting for {config.MIN_CONSECUTIVE_GOOD_READINGS - count} "
                f"more consecutive good readings before registering {base_token}"
            )
            continue

        # Enough consecutive readings — register if not already and push data
        await _register_pair(pair)

        candidate_id  = _compute_candidate_id(base_token, pair["fee"], pair["tick_spacing"])
        volume_usd    = int(data["volume_usd"])
        liquidity_usd = int(data["liquidity_usd"])

        log.info(f"Pushing pool data | {base_token} volume=${volume_usd:,} liquidity=${liquidity_usd:,}")

        await _send_tx(
            config.strategy_manager.functions.updatePoolData(
                candidate_id,
                volume_usd,
                liquidity_usd,
                0,  # ourRoutedVolumeUsd — add event-based tracking post-launch
            )
        )


async def evaluate_and_deploy() -> None:
    """
    Call evaluateAndMigrate. If the contract migrates,
    immediately deploy the new position.
    """
    active_before = config.strategy_manager.functions.getActiveCandidate().call()
    deadline      = _deadline()

    log.info("Calling evaluateAndMigrate...")
    await _send_tx(
        config.strategy_manager.functions.evaluateAndMigrate(deadline)
    )

    active_after = config.strategy_manager.functions.getActiveCandidate().call()

    if active_after != active_before and active_after != b"\x00" * 32:
        log.info(f"Migration detected — deploying new position for {active_after.hex()}")
        await deploy_active_candidate(active_after)


async def deploy_active_candidate(active_id: bytes | None = None) -> None:
    """
    Deploy the active candidate position.
    Fetches current price and computes ticks before calling the contract.
    """
    if active_id is None:
        active_id = config.strategy_manager.functions.getActiveCandidate().call()

    if active_id == b"\x00" * 32:
        log.warning("No active candidate to deploy")
        return

    # Find the matching whitelisted pair
    active_pair = None
    for pair in config.WHITELISTED_PAIRS:
        cid = _compute_candidate_id(pair["base_token"], pair["fee"], pair["tick_spacing"])
        if cid == active_id:
            active_pair = pair
            break

    if not active_pair:
        log.error(f"Active candidate {active_id.hex()} not in WHITELISTED_PAIRS — refusing to deploy")
        return

    # Fetch current price
    data = await fetch_pool_data(active_pair["pool_address"])
    if not data or data["price"] <= 0:
        log.error("Cannot deploy — no valid price data from GeckoTerminal")
        return

    current_price  = data["price"]
    tick_lower, tick_upper = compute_tick_range(
        current_price=current_price,
        tick_spacing=active_pair["tick_spacing"],
        range_width_bps=config.RANGE_WIDTH_BPS,
    )
    sqrt_price_x96 = compute_sqrt_price_x96_from_price(current_price)
    deadline       = _deadline()

    log.info(
        f"Deploying position | pair={active_pair['base_token']} "
        f"price={current_price:.6f} tickLower={tick_lower} tickUpper={tick_upper}"
    )

    await _send_tx(
        config.strategy_manager.functions.deployActiveCandidate(
            sqrt_price_x96,
            tick_lower,
            tick_upper,
            False,  # set True only if pool needs initialization
            deadline,
        )
    )


async def run_scheduler() -> None:
    """
    Main scheduler loop. Runs every UPDATE_INTERVAL_SECONDS.
    """
    log.info(
        f"Scheduler starting | {len(config.WHITELISTED_PAIRS)} whitelisted pairs | "
        f"interval={config.UPDATE_INTERVAL_SECONDS}s | "
        f"min_consecutive={config.MIN_CONSECUTIVE_GOOD_READINGS}"
    )

    while True:
        try:
            log.info("--- Scheduler tick ---")
            await update_pool_data()
            await evaluate_and_deploy()
            log.info(f"Tick done. Sleeping {config.UPDATE_INTERVAL_SECONDS}s...")

        except Exception as e:
            log.error(f"Scheduler error: {e}", exc_info=True)

        await asyncio.sleep(config.UPDATE_INTERVAL_SECONDS)