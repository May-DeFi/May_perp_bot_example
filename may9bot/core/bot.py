import asyncio
import json
import time
import websockets
from datetime import datetime

from core.backend_client import BackendClient
from core.config_manager import BACKEND_HTTP_URL, BACKEND_WS_URL
from core.position_tracker import PositionTracker, Position
from core.signal_executor import SignalExecutor
from core.monitor import Monitor
from core.trade_log import TradeLog
from core.price_feed import fetch_all_prices, build_price_map


class Bot:
    def __init__(self, config: dict, terminal):
        self.cfg        = config
        self.terminal   = terminal
        self.client     = BackendClient(
            http_url=BACKEND_HTTP_URL,
            bot_secret=config["bot_secret"],
            mode=config["mode"],
        )
        self.tracker    = PositionTracker()
        self.trade_log  = TradeLog()
        self._pair_map: dict          = {}
        self._pair_map_inverted: dict = {}
        self._start_time              = time.time()
        self._monitor: Monitor | None = None

    async def _init(self):
        self.terminal.print_info("Fetching pair list from backend...")
        try:
            self._pair_map          = await self.client.get_pair_map()
            self._pair_map_inverted = {v: k for k, v in self._pair_map.items()}
            self.terminal.print_success(f"Loaded {len(self._pair_map)} trading pairs")
        except Exception as e:
            self.terminal.print_error(f"Failed to load pairs: {e}")
            raise

        self.terminal.print_info("Recovering open positions...")
        try:
            trades = await self.client.get_positions()
            self.tracker.restore_from_backend(trades, self._pair_map_inverted)
            if self.tracker.count() > 0:
                self.terminal.print_success(f"Recovered {self.tracker.count()} open position(s)")
            else:
                self.terminal.print_info("No open positions to recover")
        except Exception as e:
            self.terminal.print_warning(f"Could not recover positions: {e}")

    async def _listen_signals(self):
        reconnect_delay = 5
        while True:
            try:
                self.terminal.print_ws_status("CONNECTING", BACKEND_WS_URL)
                async with websockets.connect(
                    BACKEND_WS_URL,
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    self.terminal.print_ws_status("CONNECTED")
                    reconnect_delay = 5

                    async for message in ws:
                        data     = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "init":
                            signals = data.get("signals", [])
                            self.terminal.print_info(
                                f"Signal feed INIT — {len(signals)} recent signal(s) "
                                f"(display only, not executed)"
                            )
                            for s in signals:
                                self.terminal.print_signal_received(s, init=True)

                        elif msg_type == "signals":
                            for s in data.get("signals", []):
                                await self._on_signal(s)

                        elif msg_type == "signal_update":
                            self.terminal.print_signal_update(data)

            except websockets.exceptions.ConnectionClosedError as e:
                self.terminal.print_ws_status("DROPPED", str(e))
            except websockets.exceptions.ConnectionClosedOK:
                self.terminal.print_ws_status("CLOSED")
            except Exception as e:
                self.terminal.print_error(f"Signal WS error: {e}")

            self.terminal.print_info(f"Signal WS reconnecting in {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)

    async def _listen_bot_events(self):
        bot_ws_url      = f"{BACKEND_WS_URL.replace('/signals/ws', '')}/trades/ws/bot"
        bot_secret      = self.cfg["bot_secret"]
        reconnect_delay = 5

        while True:
            try:
                self.terminal.print_info("Connecting to bot event stream...")
                async with websockets.connect(
                    bot_ws_url,
                    additional_headers={"X-Bot-Secret": bot_secret},
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    self.terminal.print_info("Bot event stream connected")
                    reconnect_delay = 5

                    async for message in ws:
                        data      = json.loads(message)
                        msg_type  = data.get("type")

                        if msg_type == "trade_opened":
                            await self._on_trade_opened(data["trade"])

                        elif msg_type == "trade_canceled":
                            self.terminal.print_warning(
                                f"Trade canceled — pair={data.get('pair_index')} "
                                f"reason={data.get('cancel_reason')}"
                            )

                        elif msg_type in ("trade_closed", "auto_close"):
                            await self._on_trade_closed(data)

            except websockets.exceptions.ConnectionClosedError as e:
                self.terminal.print_warning(f"Bot event stream dropped: {e}")
            except websockets.exceptions.ConnectionClosedOK:
                self.terminal.print_warning("Bot event stream closed by server")
            except Exception as e:
                self.terminal.print_error(f"Bot event stream error: {e}")

            self.terminal.print_info(f"Bot event stream reconnecting in {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)

    async def _on_trade_opened(self, trade: dict):
        pair_index  = trade.get("pair_index")
        trade_index = trade.get("trade_index")
        pair_name   = self._pair_map_inverted.get(pair_index, f"PAIR_{pair_index}")
        parts       = pair_name.split("/")
        from_asset  = parts[0] if len(parts) == 2 else pair_name
        to_asset    = parts[1] if len(parts) == 2 else "USD"

        existing = None
        for pos in self.tracker.get_all():
            if pos.pair == pair_name and pos.trade_index == 0:
                existing = pos
                break

        if existing:
            existing.trade_index  = trade_index
            existing.entry_price  = trade.get("open_price", existing.entry_price)
            existing.sl_price     = trade.get("sl", existing.sl_price)
            existing.tp_price     = trade.get("tp", existing.tp_price)
            self.terminal.print_success(
                f"Trade confirmed on-chain — {pair_name} "
                f"trade_index={trade_index} "
                f"entry={existing.entry_price:,.4f}"
            )
            self.trade_log.update_trade_index(pair_index, trade_index)
        else:
            pos = Position(
                pair        = pair_name,
                from_asset  = from_asset,
                to_asset    = to_asset,
                pair_id     = pair_index,
                trade_index = trade_index,
                direction   = trade.get("is_buy", True),
                entry_price = trade.get("open_price", 0),
                collateral  = trade.get("collateral", 0),
                leverage    = int(trade.get("leverage", 1)),
                sl_price    = trade.get("sl", 0),
                tp_price    = trade.get("tp", 0),
                tx_hash     = "from_chain",
            )
            self.tracker.add(pos)
            self.terminal.print_success(
                f"New position from chain — {pair_name} trade_index={trade_index}"
            )

    async def _on_trade_closed(self, data: dict):
        trade_id       = data.get("trade_id")
        percent_profit = data.get("percent_profit", 0)
        close_type     = data.get("close_type", "MARKET")
        price          = data.get("price", 0)

        pos = self.tracker.get(trade_id, trade_id)
        if pos:
            self.trade_log.record_close(
                pair_id     = pos.pair_id,
                trade_index = pos.trade_index,
                exit_price  = price,
                pnl_pct     = percent_profit,
                reason      = close_type,
            )
            self.tracker.remove(pos.pair_id, pos.trade_index)
            self.terminal.print_info(
                f"Position closed — {pos.pair} "
                f"pnl={percent_profit:+.2f}% "
                f"type={close_type}"
            )

    async def _on_signal(self, signal: dict):
        executor = SignalExecutor(
            client    = self.client,
            tracker   = self.tracker,
            pair_map  = self._pair_map,
            config    = self.cfg,
            terminal  = self.terminal,
            trade_log = self.trade_log,
        )
        await executor.execute(signal)

    async def _refresh_pair_map(self):
        while True:
            await asyncio.sleep(600)
            try:
                self._pair_map          = await self.client.get_pair_map()
                self._pair_map_inverted = {v: k for k, v in self._pair_map.items()}
                self.terminal.print_info(f"Pair map refreshed — {len(self._pair_map)} pairs")
            except Exception as e:
                self.terminal.print_warning(f"Pair map refresh failed: {e}")

    async def _refresh_status(self):
        while True:
            await asyncio.sleep(5)
            uptime    = int(time.time() - self._start_time)
            positions = self.tracker.get_all()
            self.terminal.update_status_bar(positions=positions, uptime=uptime)

    async def run(self):
        try:
            await self._init()
        except Exception as e:
            self.terminal.print_error(f"Initialization failed: {e}")
            input("\nPress Enter to return to menu...")
            return

        self._monitor = Monitor(
            tracker  = self.tracker,
            client   = self.client,
            config   = self.cfg,
            terminal = self.terminal,
        )

        self.terminal.print_bot_started()

        try:
            await asyncio.gather(
                self._listen_signals(),
                self._listen_bot_events(),
                self._monitor.run(),
                self._refresh_pair_map(),
                self._refresh_status(),
            )
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            self.terminal.print_info("Bot stopped by user.")
        finally:
            if self._monitor:
                self._monitor.stop()

    async def show_positions(self):
        try:
            self._pair_map          = await self.client.get_pair_map()
            self._pair_map_inverted = {v: k for k, v in self._pair_map.items()}
            trades                  = await self.client.get_positions()
            self.tracker.restore_from_backend(trades, self._pair_map_inverted)
        except Exception as e:
            self.terminal.print_error(f"Failed to fetch positions: {e}")

        prices_raw = await fetch_all_prices()
        price_map  = build_price_map(prices_raw)

        for pos in self.tracker.get_all():
            current = price_map.get(pos.pair)
            if current:
                self.tracker.update_price(pos.pair, current)

        self.terminal.show_positions_table(self.tracker.get_all())
        input("\nPress Enter to return to menu...")