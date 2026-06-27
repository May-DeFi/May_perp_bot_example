import aiohttp
import json
from typing import Optional


class BackendClient:
    def __init__(self, http_url: str, bot_secret: str, mode: str):
        self.base = http_url.rstrip("/")
        self.headers = {
            "X-Bot-Secret": bot_secret,
            "Content-Type": "application/json",
        }
        self.mode = mode

    async def _post(self, path: str, body: dict) -> dict:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.base}{path}",
                json=body,
                headers=self.headers,
            ) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    raise Exception(f"HTTP {resp.status}: {text[:300]}")
                if resp.status not in (200, 201):
                    raise Exception(data.get("message") or data.get("detail") or f"HTTP {resp.status}: {text[:200]}")
                return data

    async def _get(self, path: str, params: dict = None, auth: bool = True) -> dict:
        timeout = aiohttp.ClientTimeout(total=30)
        headers = self.headers if auth else {"Content-Type": "application/json"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{self.base}{path}",
                params=params,
                headers=headers,
            ) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except Exception:
                    raise Exception(f"HTTP {resp.status}: {text[:300]}")
                if resp.status != 200:
                    raise Exception(data.get("message") or data.get("detail") or f"HTTP {resp.status}: {text[:200]}")
                return data

    async def get_pair_map(self) -> dict[str, int]:
        """
        Returns { 'BTC/USD': pair_id, ... }
        Uses GET /prices/pairs — lightweight subgraph call, no per-pair price fetching.
        Not auth-protected so called without bot secret.
        """
        data = await self._get("/prices/pairs", params={"mode": self.mode}, auth=False)
        pairs = data.get("data", {}).get("pairs", [])
        result = {}
        for p in pairs:
            from_a = p.get("from", "")
            to_a   = p.get("to", "")
            pid    = p.get("id")
            if from_a and to_a and pid is not None:
                result[f"{from_a}/{to_a}"] = int(pid)
        return result

    async def open_trade(self, pair_id: int, collateral: float, leverage: int,
                         direction: bool, tp_price: Optional[float] = None,
                         sl_price: Optional[float] = None) -> dict:
        body = {
            "action": "open",
            "pair_id": pair_id,
            "collateral": collateral,
            "leverage": leverage,
            "direction": direction,
            "order_type": "MARKET",
        }
        result = await self._post("/bot/signal", body)
        return result.get("data", {})

    async def update_sl(self, pair_id: int, trade_index: int, sl_price: float) -> dict:
        body = {
            "action": "update_sl",
            "pair_id": pair_id,
            "trade_index": trade_index,
            "sl_price": sl_price,
        }
        result = await self._post("/bot/signal", body)
        return result.get("data", {})

    async def update_tp(self, pair_id: int, trade_index: int, tp_price: float) -> dict:
        body = {
            "action": "update_tp",
            "pair_id": pair_id,
            "trade_index": trade_index,
            "tp_price": tp_price,
        }
        result = await self._post("/bot/signal", body)
        return result.get("data", {})

    async def get_positions(self) -> list:
        body = {"action": "positions", "pair_id": 0}
        result = await self._post("/bot/signal", body)
        return result.get("data", {}).get("trades", [])