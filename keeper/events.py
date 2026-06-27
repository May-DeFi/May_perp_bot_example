"""
events.py — Alchemy WebSocket listener.

Subscribes to HookContract logs and responds to:
  - RangeRepositionFlagged  → reposition the LP range
  - RatioRebalanceFlagged   → log and monitor

Price data is always fetched using the active pair's pool_address
from WHITELISTED_PAIRS — never any other address.
"""

import asyncio
import logging
from web3 import AsyncWeb3
from web3.providers import WebSocketProvider

import config
from pool_data import fetch_pool_data, get_active_pair_pool_address
from ticks import compute_tick_range, compute_sqrt_price_x96_from_price

log = logging.getLogger(__name__)


async def handle_range_reposition(event: dict) -> None:
    """
    RangeRepositionFlagged fired — price drifted beyond threshold.
    Steps:
      1. Get active pair pool address from WHITELISTED_PAIRS
      2. Fetch current price from GeckoTerminal for that pool
      3. Compute new tick range centered on current price
      4. Call deployActiveCandidate with new ticks
    """
    args       = event["args"]
    old_center = args["oldCenter"]
    new_center = args["newCenter"]
    drift      = args["drift"]

    log.info(
        f"RangeRepositionFlagged | oldCenter={old_center} "
        f"newCenter={new_center} drift={drift} "
        f"({'above' if drift > 0 else 'below'} center)"
    )

    # Get the active pair's pool address from whitelist
    pool_address = get_active_pair_pool_address()
    if not pool_address:
        log.warning("No active whitelisted pair found — skipping reposition")
        return

    # Get the full pair config for tick_spacing
    active_pair = None
    for pair in config.WHITELISTED_PAIRS:
        if pair["pool_address"].lower() == pool_address.lower():
            active_pair = pair
            break

    if not active_pair:
        log.error(f"Pool {pool_address} not found in WHITELISTED_PAIRS — skipping")
        return

    # Fetch current price using the whitelisted pool address
    data = await fetch_pool_data(pool_address)
    if not data or data["price"] <= 0:
        log.error(f"No valid price data for {pool_address} — skipping reposition")
        return

    current_price = data["price"]
    tick_lower, tick_upper = compute_tick_range(
        current_price=current_price,
        tick_spacing=active_pair["tick_spacing"],
        range_width_bps=config.RANGE_WIDTH_BPS,
    )
    sqrt_price_x96 = compute_sqrt_price_x96_from_price(current_price)
    deadline       = _deadline()

    log.info(
        f"Repositioning | price={current_price:.6f} "
        f"tickLower={tick_lower} tickUpper={tick_upper}"
    )

    await _send_tx(
        config.strategy_manager.functions.deployActiveCandidate(
            sqrt_price_x96,
            tick_lower,
            tick_upper,
            False,
            deadline,
        )
    )


async def handle_ratio_rebalance(event: dict) -> None:
    """
    RatioRebalanceFlagged fired — token ratio drifted.
    Logged for monitoring. The next reposition corrects the ratio naturally.
    """
    args = event["args"]
    log.warning(
        f"RatioRebalanceFlagged | "
        f"amount0={args['amount0']} "
        f"amount1={args['amount1']} "
        f"driftBps={args['driftBps']}"
    )


async def listen_for_events() -> None:
    """
    Main WebSocket loop. Subscribes to HookContract logs.
    Reconnects automatically if the connection drops.
    """
    reposition_sig = config.hook_contract.events.RangeRepositionFlagged().event_topic
    ratio_sig      = config.hook_contract.events.RatioRebalanceFlagged().event_topic

    while True:
        try:
            log.info("Connecting to Alchemy WebSocket...")
            async with AsyncWeb3(WebSocketProvider(config.ALCHEMY_WSS_URL)) as w3:
                log.info("WebSocket connected. Subscribing to HookContract logs...")

                subscription_id = await w3.eth.subscribe(
                    "logs",
                    {
                        "address": config.HOOK_CONTRACT,
                        "topics":  [[reposition_sig, ratio_sig]],
                    },
                )
                log.info(f"Subscribed — id={subscription_id.hex()}")

                async for message in w3.socket.process_subscriptions():
                    try:
                        result = message["result"]
                        topic  = result["topics"][0].hex()

                        if topic == reposition_sig.hex():
                            event = config.hook_contract.events.RangeRepositionFlagged().process_log(result)
                            await handle_range_reposition(event)

                        elif topic == ratio_sig.hex():
                            event = config.hook_contract.events.RatioRebalanceFlagged().process_log(result)
                            await handle_ratio_rebalance(event)

                    except Exception as e:
                        log.error(f"Error processing event: {e}", exc_info=True)

        except Exception as e:
            log.error(f"WebSocket error: {e} — reconnecting in 5s", exc_info=True)
            await asyncio.sleep(5)


def _deadline() -> int:
    """Current block timestamp + buffer as transaction deadline."""
    return config.w3.eth.get_block("latest")["timestamp"] + config.DEADLINE_BUFFER_SECONDS


async def _send_tx(fn) -> None:
    """Sign and broadcast a contract transaction."""
    try:
        tx = fn.build_transaction({
            "from":  config.KEEPER_ADDRESS,
            "nonce": config.w3.eth.get_transaction_count(config.KEEPER_ADDRESS),
            "gas":   500_000,
        })
        signed  = config.w3.eth.account.sign_transaction(tx, config.KEEPER_PRIVATE_KEY)
        tx_hash = config.w3.eth.send_raw_transaction(signed.raw_transaction)
        log.info(f"Tx sent: {tx_hash.hex()}")

        receipt = config.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt["status"] == 1:
            log.info(f"Tx confirmed: {tx_hash.hex()}")
        else:
            log.error(f"Tx reverted: {tx_hash.hex()}")

    except Exception as e:
        log.error(f"Transaction failed: {e}", exc_info=True)

        