import json
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trade_log.json")


class TradeLog:
    def __init__(self):
        self.path = os.path.abspath(LOG_FILE)

    def _load(self) -> list:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, records: list):
        with open(self.path, "w") as f:
            json.dump(records, f, indent=2)

    def record_open(self, pair: str, direction: str, entry_price: float,
                    collateral: float, leverage: int, sl_price: float,
                    tp_price: float, pair_id: int, trade_index: int,
                    tx_hash: str):
        records = self._load()
        records.append({
            "id": len(records) + 1,
            "pair": pair,
            "direction": direction,
            "entry_price": entry_price,
            "collateral": collateral,
            "leverage": leverage,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "pair_id": pair_id,
            "trade_index": trade_index,
            "tx_hash": tx_hash,
            "opened_at": datetime.now().isoformat(),
            "closed_at": None,
            "exit_price": None,
            "pnl_pct": None,
            "status": "OPEN",
        })
        self._save(records)

    def record_close(self, pair_id: int, trade_index: int,
                     exit_price: float, pnl_pct: float, reason: str):
        records = self._load()
        for r in records:
            if r["pair_id"] == pair_id and r["trade_index"] == trade_index and r["status"] == "OPEN":
                r["status"] = "CLOSED"
                r["exit_price"] = exit_price
                r["pnl_pct"] = round(pnl_pct, 4)
                r["closed_at"] = datetime.now().isoformat()
                r["close_reason"] = reason
                break
        self._save(records)

    def update_trade_index(self, pair_id: int, trade_index: int):
        """Once MarketOpenExecuted fires, update the confirmed trade_index."""
        records = self._load()
        for r in records:
            if r["pair_id"] == pair_id and r["trade_index"] == 0 and r["status"] == "OPEN":
                r["trade_index"] = trade_index
                break
        self._save(records)

    def get_all(self) -> list:
        return self._load()

    def get_open(self) -> list:
        return [r for r in self._load() if r["status"] == "OPEN"]