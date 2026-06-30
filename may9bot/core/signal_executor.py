import asyncio
from core.backend_client import BackendClient
from core.position_tracker import PositionTracker, Position
from core.price_feed import fetch_all_prices, get_mid_price
from core.trade_log import TradeLog


class SignalExecutor:
    def __init__(self, client: BackendClient, tracker: PositionTracker,
                 pair_map: dict, config: dict, terminal, trade_log: TradeLog):
        self.client    = client
        self.tracker   = tracker
        self.pair_map  = pair_map
        self.cfg       = config
        self.terminal  = terminal
        self.trade_log = trade_log

    async def execute(self, signal: dict):
        pair          = signal.get("pair", "")
        direction_str = signal.get("direction", "").upper()
        sig_tp        = float(signal.get("tp") or 0)
        sig_sl        = float(signal.get("sl") or 0)

        pair_id = self.pair_map.get(pair)
        if pair_id is None:
            self.terminal.print_warning(f"Signal pair '{pair}' not supported — skipping")
            return

        direction = True if direction_str == "LONG" else False

        prices_raw    = await fetch_all_prices()
        parts         = pair.split("/")
        from_asset    = parts[0] if len(parts) == 2 else pair
        to_asset      = parts[1] if len(parts) == 2 else "USD"
        current_price = get_mid_price(prices_raw, from_asset, to_asset)

        if current_price is None or current_price == 0:
            self.terminal.print_warning(f"Cannot get price for {pair} — skipping")
            return

        # SL
        if sig_sl and sig_sl > 0:
            sl_price = sig_sl
        else:
            sl_pct   = self.cfg.get("sl_percent", 2.0)
            sl_price = current_price * (1 - sl_pct / 100) if direction else current_price * (1 + sl_pct / 100)

        # TP
        if sig_tp and sig_tp > 0:
            tp_price = sig_tp
        else:
            tp_pct   = self.cfg.get("tp_percent", 4.0)
            tp_price = current_price * (1 + tp_pct / 100) if direction else current_price * (1 - tp_pct / 100)

        collateral = self.cfg.get("collateral_usdc", 10.0)
        leverage   = 10

        self.terminal.print_signal_received(signal)

        try:
            result = await self.client.open_trade(
                pair_id   = pair_id,
                collateral = collateral,
                leverage   = leverage,
                direction  = direction,
                tp_price   = tp_price,
                sl_price   = sl_price,
            )

            tx_hash = result.get("tx_hash", "")

            pos = Position(
                pair        = pair,
                from_asset  = from_asset,
                to_asset    = to_asset,
                pair_id     = pair_id,
                trade_index = 0,
                direction   = direction,
                entry_price = current_price,
                collateral  = collateral,
                leverage    = leverage,
                sl_price    = sl_price,
                tp_price    = tp_price,
                tx_hash     = tx_hash,
            )
            self.tracker.add(pos)

            self.trade_log.record_open(
                pair        = pair,
                direction   = "LONG" if direction else "SHORT",
                entry_price = current_price,
                collateral  = collateral,
                leverage    = leverage,
                sl_price    = sl_price,
                tp_price    = tp_price,
                pair_id     = pair_id,
                trade_index = 0,
                tx_hash     = tx_hash,
            )

            self.terminal.print_trade_opened(
                pair      = pair,
                direction = "LONG" if direction else "SHORT",
                entry     = current_price,
                sl        = sl_price,
                tp        = tp_price,
                collateral = collateral,
                leverage   = leverage,
                tx_hash    = tx_hash,
            )

            asyncio.create_task(
                self._resolve_trade_index(pos, pair_id, direction)
            )

        except Exception as e:
            self.terminal.print_error(f"Trade execution failed [{pair}]: {e}")

    async def _resolve_trade_index(self, pos: Position, pair_id: int, direction: bool):
        delays = [2, 4, 8, 16, 30]

        for attempt, delay in enumerate(delays, 1):
            await asyncio.sleep(delay)

            try:
                trades = await self.client.get_positions()
            except Exception as e:
                self.terminal.print_warning(
                    f"[trade_index] Poll attempt {attempt} failed [{pos.pair}]: {e}"
                )
                continue

            match = None
            for t in trades:
                t_pair_id  = int(t.get("pair", {}).get("id") or t.get("pairIndex", -1))
                t_is_buy   = bool(t.get("isBuy", t.get("is_buy", True)))
                t_index    = int(t.get("index", -1))

                if t_pair_id == pair_id and t_is_buy == direction and t_index >= 0:
                    existing = self.tracker.get(pair_id, t_index)
                    if existing is None:
                        match = t
                        break

            if match is None:
                self.terminal.print_warning(
                    f"[trade_index] Attempt {attempt}/{len(delays)} — "
                    f"no match yet for {pos.pair} "
                    f"({'LONG' if direction else 'SHORT'}) "
                    f"retrying in {delays[attempt] if attempt < len(delays) else 0}s..."
                ) if attempt < len(delays) else None
                continue

            confirmed_index = int(match.get("index", 0))

            pos.trade_index = confirmed_index
            self.tracker.remove(pair_id, 0)
            self.tracker.add(pos)

            self.trade_log.update_trade_index(pair_id, confirmed_index)

            self.terminal.print_success(
                f"[trade_index] Confirmed {pos.pair} "
                f"trade_index={confirmed_index} "
                f"(attempt {attempt}, after {sum(delays[:attempt])}s)"
            )
            return

        self.terminal.print_error(
            f"[trade_index] Could not resolve trade_index for {pos.pair} "
            f"after {sum(delays)}s — position remains at index=0. "
            f"SL/TP updates will fail until bot restarts."
        )