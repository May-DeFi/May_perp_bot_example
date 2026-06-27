from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    pair: str           # e.g. "BTC/USD"
    from_asset: str     # e.g. "BTC"
    to_asset: str       # e.g. "USD"
    pair_id: int
    trade_index: int
    direction: bool     # True = LONG, False = SHORT
    entry_price: float
    collateral: float
    leverage: int
    sl_price: float
    tp_price: float
    tx_hash: str

    # Runtime state
    current_price: float = 0.0
    pnl_pct: float = 0.0
    breakeven_set: bool = False
    trailing_active: bool = False
    trailing_sl: float = 0.0


class PositionTracker:
    def __init__(self):
        self._positions: list[Position] = []

    def add(self, pos: Position):
        self._positions.append(pos)

    def remove(self, pair_id: int, trade_index: int):
        self._positions = [
            p for p in self._positions
            if not (p.pair_id == pair_id and p.trade_index == trade_index)
        ]

    def get_all(self) -> list[Position]:
        return list(self._positions)

    def get(self, pair_id: int, trade_index: int) -> Optional[Position]:
        for p in self._positions:
            if p.pair_id == pair_id and p.trade_index == trade_index:
                return p
        return None

    def count(self) -> int:
        return len(self._positions)

    def update_price(self, pair: str, current_price: float):
        """Update price and recalculate PnL% for all positions on this pair."""
        for pos in self._positions:
            if pos.pair == pair and pos.entry_price > 0 and current_price > 0:
                pos.current_price = current_price
                price_move_pct = (current_price - pos.entry_price) / pos.entry_price * 100
                if pos.direction:  # LONG
                    pos.pnl_pct = price_move_pct * pos.leverage
                else:              # SHORT
                    pos.pnl_pct = -price_move_pct * pos.leverage

    def restore_from_backend(self, trades: list, pair_map_inverted: dict):
        """
        Rebuild in-memory state from backend positions response on bot restart.
        pair_map_inverted: { pair_id: 'BTC/USD' }
        """
        self._positions = []
        for t in trades:
            try:
                pair_id = int(t.get("pair", {}).get("id") or t.get("pairIndex", 0))
                trade_index = int(t.get("index", 0))
                pair_name = pair_map_inverted.get(pair_id, f"PAIR_{pair_id}")
                parts = pair_name.split("/")
                from_asset = parts[0] if len(parts) == 2 else pair_name
                to_asset = parts[1] if len(parts) == 2 else "USD"

                entry_price = float(t.get("openPrice", 0)) / 1e18
                leverage = int(float(t.get("leverage", 100)) / 100)
                direction = bool(t.get("isBuy", t.get("is_buy", True)))
                collateral = float(t.get("collateralAfterFees", t.get("collateral", 0))) / 1e6
                sl_price = float(t.get("sl", 0)) / 1e18
                tp_price = float(t.get("tp", 0)) / 1e18

                pos = Position(
                    pair=pair_name,
                    from_asset=from_asset,
                    to_asset=to_asset,
                    pair_id=pair_id,
                    trade_index=trade_index,
                    direction=direction,
                    entry_price=entry_price,
                    collateral=collateral,
                    leverage=leverage,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    tx_hash="recovered",
                )
                self._positions.append(pos)
            except Exception:
                continue
