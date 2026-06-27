import aiohttp
import ssl
from typing import Optional

PRICE_URL = "https://metadata-backend.ostium.io/PricePublish/latest-prices"


async def fetch_all_prices() -> list[dict]:
    """
    Returns list of:
    { 'from': 'BTC', 'to': 'USD', 'mid': 107646.03, 'bid': ..., 'ask': ...,
      'isMarketOpen': True, 'timestampSeconds': ... }
    """
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    timeout = aiohttp.ClientTimeout(total=5)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(PRICE_URL) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
    except Exception:
        return []


def get_mid_price(prices: list[dict], from_asset: str, to_asset: str) -> Optional[float]:
    """Extract mid price for a given pair from the prices list."""
    for p in prices:
        if p.get("from") == from_asset and p.get("to") == to_asset:
            return float(p.get("mid", 0))
    return None


def build_price_map(prices: list[dict]) -> dict[str, float]:
    """Build { 'BTC/USD': 107646.03, ... } lookup."""
    result = {}
    for p in prices:
        key = f"{p.get('from')}/{p.get('to')}"
        result[key] = float(p.get("mid", 0))
    return result
