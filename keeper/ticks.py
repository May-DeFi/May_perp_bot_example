"""
ticks.py — tick and sqrtPrice math helpers.

All math mirrors what Uniswap v4 does on-chain so the keeper computes
the same values the contracts expect.
"""

import math

MIN_TICK = -887272
MAX_TICK =  887272
Q96      = 2 ** 96


def price_to_sqrt_price_x96(price: float) -> int:
    """
    Convert a human-readable price (token1 per token0) to sqrtPriceX96.
    price must already be adjusted for token decimals.
    """
    return int(math.sqrt(price) * Q96)


def sqrt_price_x96_to_price(sqrt_price_x96: int) -> float:
    """Convert sqrtPriceX96 back to a human-readable price."""
    return (sqrt_price_x96 / Q96) ** 2


def price_to_tick(price: float) -> int:
    """Convert a price to the nearest valid tick."""
    tick = math.floor(math.log(price) / math.log(1.0001))
    return max(MIN_TICK, min(MAX_TICK, tick))


def tick_to_price(tick: int) -> float:
    """Convert a tick to its corresponding price."""
    return 1.0001 ** tick


def nearest_usable_tick(tick: int, tick_spacing: int) -> int:
    """Round a tick to the nearest multiple of tick_spacing."""
    rounded = round(tick / tick_spacing) * tick_spacing
    return max(MIN_TICK, min(MAX_TICK, rounded))


def compute_tick_range(
    current_price: float,
    tick_spacing: int,
    range_width_bps: int = 1000,
) -> tuple[int, int]:
    """
    Compute tickLower and tickUpper centered on current_price.

    range_width_bps: half-width of the range in basis points.
                     1000 bps = 10%, so total range is ±10% around current price.

    Returns (tickLower, tickUpper) both snapped to tick_spacing.
    """
    center_tick = price_to_tick(current_price)

    # Convert bps to a price multiplier for the half-width
    # e.g. 1000 bps = 10% → lower price = current * 0.90, upper = current * 1.10
    half_width = range_width_bps / 10_000

    lower_price = current_price * (1 - half_width)
    upper_price = current_price * (1 + half_width)

    tick_lower = nearest_usable_tick(price_to_tick(lower_price), tick_spacing)
    tick_upper = nearest_usable_tick(price_to_tick(upper_price), tick_spacing)

    # Safety: ensure valid range
    if tick_lower >= tick_upper:
        tick_lower = nearest_usable_tick(center_tick - tick_spacing, tick_spacing)
        tick_upper = nearest_usable_tick(center_tick + tick_spacing, tick_spacing)

    return tick_lower, tick_upper


def compute_sqrt_price_x96_from_price(price: float) -> int:
    """Full pipeline: human price → sqrtPriceX96 ready for the contract."""
    return price_to_sqrt_price_x96(price)
