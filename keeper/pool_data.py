"""
pool_data.py — fetches volume, liquidity, price and age from GeckoTerminal.

Only fetches data for pools that are in WHITELISTED_PAIRS.
Any attempt to fetch a non-whitelisted pool raises immediately.

GeckoTerminal free API, no key required.
Base network identifier: "base"
"""

import aiohttp
import logging
from datetime import datetime, timezone

import config

log = logging.getLogger(__name__)

GECKO_BASE_URL = "https://api.geckoterminal.com/api/v2"
NETWORK        = "base"

# Build a set of whitelisted pool addresses at import time for O(1) lookup
_WHITELISTED_POOL_ADDRESSES: set[str] = {
    p["pool_address"].lower() for p in config.WHITELISTED_PAIRS
}


def _assert_whitelisted(pool_address: str) -> None:
    """Raise immediately if pool_address is not in WHITELISTED_PAIRS."""
    if pool_address.lower() not in _WHITELISTED_POOL_ADDRESSES:
        raise ValueError(
            f"fetch_pool_data called with non-whitelisted pool {pool_address}. "
            "Add it to WHITELISTED_PAIRS in .env first."
        )


async def fetch_pool_data(pool_address: str) -> dict | None:
    """
    Fetch volume, liquidity, price and age for a whitelisted pool on Base.

    Raises ValueError if pool_address is not in WHITELISTED_PAIRS.

    Returns:
        {
            "volume_usd":    float,
            "liquidity_usd": float,
            "price":         float,
            "pool_age_days": int,
        }
        or None if the GeckoTerminal request fails.
    """
    _assert_whitelisted(pool_address)

    url = f"{GECKO_BASE_URL}/networks/{NETWORK}/pools/{pool_address.lower()}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    log.warning(f"GeckoTerminal returned {resp.status} for {pool_address}")
                    return None

                data  = await resp.json()
                attrs = data["data"]["attributes"]

                volume_usd    = float(attrs.get("volume_usd", {}).get("h24", 0) or 0)
                liquidity_usd = float(attrs.get("reserve_in_usd", 0) or 0)
                price         = float(attrs.get("base_token_price_quote_token", 0) or 0)

                created_at_str = attrs.get("pool_created_at", None)
                if created_at_str:
                    created_at    = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    pool_age_days = (datetime.now(timezone.utc) - created_at).days
                else:
                    pool_age_days = 0

                return {
                    "volume_usd":    volume_usd,
                    "liquidity_usd": liquidity_usd,
                    "price":         price,
                    "pool_age_days": pool_age_days,
                }

    except aiohttp.ClientError as e:
        log.error(f"Network error fetching pool {pool_address}: {e}")
        return None
    except (KeyError, ValueError) as e:
        log.error(f"Unexpected GeckoTerminal response for {pool_address}: {e}")
        return None


def passes_migration_filters(data: dict) -> tuple[bool, str]:
    """
    Run all migration quality filters against a pool's current data.
    Returns (passes: bool, reason: str).
    """
    if data["pool_age_days"] < config.MIN_POOL_AGE_DAYS:
        return False, f"pool too young ({data['pool_age_days']}d < {config.MIN_POOL_AGE_DAYS}d)"

    if data["volume_usd"] < config.MIN_DAILY_VOLUME_USD:
        return False, f"volume too low (${data['volume_usd']:,.0f} < ${config.MIN_DAILY_VOLUME_USD:,.0f})"

    if data["liquidity_usd"] < config.MIN_LIQUIDITY_USD:
        return False, f"liquidity too low (${data['liquidity_usd']:,.0f} < ${config.MIN_LIQUIDITY_USD:,.0f})"

    if data["liquidity_usd"] > 0:
        ratio = data["volume_usd"] / data["liquidity_usd"]
        if ratio < config.MIN_VOLUME_TVL_RATIO:
            return False, f"volume/TVL ratio too low ({ratio:.2f} < {config.MIN_VOLUME_TVL_RATIO})"

    return True, "ok"


def get_pair_by_pool_address(pool_address: str) -> dict | None:
    """
    Return the whitelisted pair dict for a given pool address.
    Returns None if not found.
    Used by events.py to get the active pair config from its pool address.
    """
    for pair in config.WHITELISTED_PAIRS:
        if pair["pool_address"].lower() == pool_address.lower():
            return pair
    return None


def get_active_pair_pool_address() -> str | None:
    """
    Get the pool_address for the currently active candidate from WHITELISTED_PAIRS.
    Matches by computing candidate_id against what StrategyManager reports.
    Returns None if no active candidate or not found in whitelist.
    """
    from web3 import Web3
    from scheduler import _compute_candidate_id

    active_id = config.strategy_manager.functions.getActiveCandidate().call()
    if active_id == b"\x00" * 32:
        return None

    for pair in config.WHITELISTED_PAIRS:
        cid = _compute_candidate_id(pair["base_token"], pair["fee"], pair["tick_spacing"])
        if cid == active_id:
            return pair["pool_address"]

    return None