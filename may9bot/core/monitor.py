import asyncio
from core.price_feed import fetch_all_prices, build_price_map
from core.position_tracker import PositionTracker, Position
from core.backend_client import BackendClient


class Monitor:
    def __init__(self, tracker: PositionTracker, client: BackendClient,
                 config: dict, terminal):
        self.tracker = tracker
        self.client = client
        self.cfg = config
        self.terminal = terminal
        self._running = False

    def stop(self):
        self._running = False

    async def run(self):
        self._running = True
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                self.terminal.print_error(f"Monitor error: {e}")
            await asyncio.sleep(2)

    async def _tick(self):
        positions = self.tracker.get_all()
        if not positions:
            return

        prices_raw = await fetch_all_prices()
        if not prices_raw:
            return

        price_map = build_price_map(prices_raw)

        for pos in positions:
            current_price = price_map.get(pos.pair)
            if current_price is None or current_price == 0:
                continue

            self.tracker.update_price(pos.pair, current_price)
            pnl_pct = pos.pnl_pct

            await self._check_breakeven(pos, pnl_pct, current_price)
            await self._check_trailing(pos, pnl_pct, current_price)

    async def _check_breakeven(self, pos: Position, pnl_pct: float, current_price: float):
        if pos.breakeven_set:
            return

        trigger = self.cfg.get("breakeven_trigger_pct", 1.0)
        offset_pct = self.cfg.get("breakeven_offset_pct", 0.1)

        if pnl_pct >= trigger:
            if pos.direction:  # LONG
                new_sl = pos.entry_price * (1 + offset_pct / 100)
            else:              # SHORT
                new_sl = pos.entry_price * (1 - offset_pct / 100)

            # Only move SL if it's better than current
            if pos.direction and new_sl > pos.sl_price:
                ok = await self._send_sl(pos, new_sl)
                if ok:
                    pos.breakeven_set = True
                    pos.sl_price = new_sl
                    self.terminal.print_breakeven(pos.pair, pos.trade_index, new_sl, pnl_pct)
            elif not pos.direction and (pos.sl_price == 0 or new_sl < pos.sl_price):
                ok = await self._send_sl(pos, new_sl)
                if ok:
                    pos.breakeven_set = True
                    pos.sl_price = new_sl
                    self.terminal.print_breakeven(pos.pair, pos.trade_index, new_sl, pnl_pct)

    async def _check_trailing(self, pos: Position, pnl_pct: float, current_price: float):
        trail_start = self.cfg.get("trailing_start_pct", 2.0)
        trail_dist = self.cfg.get("trailing_distance_pct", 1.0)
        hybrid_switch = self.cfg.get("trailing_hybrid_switch_pct", 4.0)

        if pnl_pct < trail_start:
            return

        # Calculate new trailing SL
        if pos.direction:  # LONG
            new_sl = current_price * (1 - trail_dist / 100)
            # Only trail if new SL is higher than current
            if new_sl <= pos.sl_price:
                return
        else:  # SHORT
            new_sl = current_price * (1 + trail_dist / 100)
            # Only trail if new SL is lower than current
            if pos.sl_price > 0 and new_sl >= pos.sl_price:
                return

        ok = await self._send_sl(pos, new_sl)
        if ok:
            old_sl = pos.sl_price
            pos.sl_price = new_sl
            pos.trailing_active = True
            pos.trailing_sl = new_sl
            self.terminal.print_trail(pos.pair, pos.trade_index, new_sl, pnl_pct)

    async def _send_sl(self, pos: Position, sl_price: float) -> bool:
        try:
            await self.client.update_sl(pos.pair_id, pos.trade_index, sl_price)
            return True
        except Exception as e:
            self.terminal.print_error(f"SL update failed [{pos.pair}#{pos.trade_index}]: {e}")
            return False
