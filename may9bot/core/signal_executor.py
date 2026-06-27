from core.backend_client import BackendClient
from core.position_tracker import PositionTracker, Position
from core.price_feed import fetch_all_prices, get_mid_price
from core.trade_log import TradeLog


class SignalExecutor:
    def __init__(self, client: BackendClient, tracker: PositionTracker,
                 pair_map: dict, config: dict, terminal, trade_log: TradeLog):
        self.client = client
        self.tracker = tracker
        self.pair_map = pair_map        # { 'BTC/USD': pair_id }
        self.cfg = config
        self.terminal = terminal
        self.trade_log = trade_log

    async def execute(self, signal: dict):
        pair = signal.get("pair", "")
        direction_str = signal.get("direction", "").upper()
        sig_tp = float(signal.get("tp") or 0)
        sig_sl = float(signal.get("sl") or 0)

        # Lookup pair_id
        pair_id = self.pair_map.get(pair)
        if pair_id is None:
            self.terminal.print_warning(f"Signal pair '{pair}' not supported — skipping")
            return

        # Map direction
        direction = True if direction_str == "LONG" else False

        # Get current price for SL/TP calculation
        prices_raw = await fetch_all_prices()
        parts = pair.split("/")
        from_asset = parts[0] if len(parts) == 2 else pair
        to_asset = parts[1] if len(parts) == 2 else "USD"
        current_price = get_mid_price(prices_raw, from_asset, to_asset)

        if current_price is None or current_price == 0:
            self.terminal.print_warning(f"Cannot get price for {pair} — skipping")
            return

        # Determine SL
        if sig_sl and sig_sl > 0:
            sl_price = sig_sl
        else:
            sl_pct = self.cfg.get("sl_percent", 2.0)
            if direction:  # LONG
                sl_price = current_price * (1 - sl_pct / 100)
            else:           # SHORT
                sl_price = current_price * (1 + sl_pct / 100)

        # Determine TP
        if sig_tp and sig_tp > 0:
            tp_price = sig_tp
        else:
            tp_pct = self.cfg.get("tp_percent", 4.0)
            if direction:  # LONG
                tp_price = current_price * (1 + tp_pct / 100)
            else:           # SHORT
                tp_price = current_price * (1 - tp_pct / 100)

        collateral = self.cfg.get("collateral_usdc", 10.0)
        leverage = int(self.cfg.get("leverage", 10))

        self.terminal.print_signal_received(signal)

        try:
            result = await self.client.open_trade(
                pair_id=pair_id,
                collateral=collateral,
                leverage=leverage,
                direction=direction,
                tp_price=tp_price,
                sl_price=sl_price,
            )

            tx_hash = result.get("tx_hash", "")
            order_id = result.get("order_id")
            # trade_index comes from order tracking — use order_id as fallback index
            trade_index = int(order_id) if order_id is not None else 0

            pos = Position(
                pair=pair,
                from_asset=from_asset,
                to_asset=to_asset,
                pair_id=pair_id,
                trade_index=trade_index,
                direction=direction,
                entry_price=current_price,
                collateral=collateral,
                leverage=leverage,
                sl_price=sl_price,
                tp_price=tp_price,
                tx_hash=tx_hash,
            )
            self.tracker.add(pos)

            self.trade_log.record_open(
                pair=pair,
                direction="LONG" if direction else "SHORT",
                entry_price=current_price,
                collateral=collateral,
                leverage=leverage,
                sl_price=sl_price,
                tp_price=tp_price,
                pair_id=pair_id,
                trade_index=trade_index,
                tx_hash=tx_hash,
            )

            self.terminal.print_trade_opened(
                pair=pair,
                direction="LONG" if direction else "SHORT",
                entry=current_price,
                sl=sl_price,
                tp=tp_price,
                collateral=collateral,
                leverage=leverage,
                tx_hash=tx_hash,
            )

        except Exception as e:
            self.terminal.print_error(f"Trade execution failed [{pair}]: {e}")
