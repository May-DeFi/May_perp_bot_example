import os
import sys
import time
from datetime import datetime
from typing import Optional

# ─── ANSI Colors ──────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

BLACK   = "\033[30m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"

BG_BLACK  = "\033[40m"
BG_GREEN  = "\033[42m"
BG_RED    = "\033[41m"
BG_YELLOW = "\033[43m"
BG_CYAN   = "\033[46m"

BRIGHT_GREEN  = "\033[92m"
BRIGHT_RED    = "\033[91m"
BRIGHT_CYAN   = "\033[96m"
BRIGHT_YELLOW = "\033[93m"
BRIGHT_WHITE  = "\033[97m"
BRIGHT_MAGENTA = "\033[95m"


def _enable_ansi_windows():
    """Enable ANSI color codes on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _clear():
    os.system("cls" if sys.platform == "win32" else "clear")


def _divider(char="─", width=70, color=DIM):
    print(f"{color}{char * width}{RESET}")


class Terminal:
    def __init__(self):
        _enable_ansi_windows()
        self._ws_status = "DISCONNECTED"
        self._position_count = 0
        self._uptime = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Banner
    # ──────────────────────────────────────────────────────────────────────────

    def print_banner(self):
        _clear()
        banner = f"""
{BRIGHT_CYAN}{BOLD}
  ███╗   ███╗ █████╗ ██╗   ██╗ █████╗
  ████╗ ████║██╔══██╗╚██╗ ██╔╝██╔══██╗
  ██╔████╔██║███████║ ╚████╔╝ ╚██████║
  ██║╚██╔╝██║██╔══██║  ╚██╔╝   ╚═══██║
  ██║ ╚═╝ ██║██║  ██║   ██║   █████╔╝
  ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚════╝
{RESET}"""
        print(banner)
        print(f"  {BRIGHT_CYAN}◆{RESET} {BOLD}Signal Bot{RESET}  {DIM}|  Powered by Ostium × MAY9{RESET}")
        print(f"  {DIM}v1.0.0  •  On-chain copy trading terminal{RESET}")
        print()
        _divider("═", 70, CYAN)
        print()

    # ──────────────────────────────────────────────────────────────────────────
    # Main Menu
    # ──────────────────────────────────────────────────────────────────────────

    def show_main_menu(self) -> str:
        print(f"\n{BOLD}{BRIGHT_CYAN}  MAIN MENU{RESET}")
        _divider()
        options = [
            ("1", "🚀", "Start Bot",          BRIGHT_GREEN),
            ("2", "⚙", "View Config",         CYAN),
            ("3", "✏", "Edit Config",         YELLOW),
            ("4", "📊", "View Open Positions", BRIGHT_CYAN),
            ("5", "📋", "Trade History",       WHITE),
            ("6", "🚪", "Exit",               DIM),
        ]
        for key, icon, label, color in options:
            print(f"  {DIM}[{RESET}{BOLD}{color}{key}{RESET}{DIM}]{RESET}  {icon}  {color}{label}{RESET}")
        _divider()
        while True:
            choice = input(f"\n  {BRIGHT_WHITE}Select option: {RESET}").strip()
            if choice in [o[0] for o in options]:
                return choice
            print(f"  {RED}Invalid option. Try again.{RESET}")

    # ──────────────────────────────────────────────────────────────────────────
    # Setup Wizard
    # ──────────────────────────────────────────────────────────────────────────

    async def run_setup_wizard(self, config_manager):
        from core.config_manager import BACKEND_HTTP_URL, BACKEND_WS_URL
        _clear()
        self.print_banner()
        print(f"  {BOLD}{BRIGHT_YELLOW}⚙  CONFIGURATION WIZARD{RESET}")
        _divider("─", 70, YELLOW)
        print(f"  {DIM}Configure your MAY9 Signal Bot. Press Enter to keep defaults.{RESET}\n")

        cfg = {}

        # Bot secret
        print(f"  {BOLD}{CYAN}── Authentication ──{RESET}")
        print(f"  {DIM}Get your Bot Secret Key from the MAY9 website under Account → API Keys{RESET}")
        cfg["bot_secret"] = self._prompt("Bot Secret Key", "")

        # Mode
        print(f"\n  {BOLD}{CYAN}── Mode ──{RESET}")
        while True:
            mode = self._prompt("Mode [mainnet / testnet]", "mainnet")
            if mode in ("mainnet", "testnet"):
                cfg["mode"] = mode
                break
            print(f"  {RED}Must be 'mainnet' or 'testnet'{RESET}")

        # Trade config
        print(f"\n  {BOLD}{CYAN}── Trade Settings ──{RESET}")
        cfg["collateral_usdc"] = float(self._prompt("Collateral per trade (USDC)", "10"))
        cfg["leverage"]        = int(self._prompt("Leverage (e.g. 10 for 10x)", "10"))

        # SL/TP
        print(f"\n  {BOLD}{CYAN}── Stop Loss / Take Profit ──{RESET}")
        print(f"  {DIM}Used when a signal arrives with sl=0 or tp=0{RESET}")
        cfg["sl_percent"] = float(self._prompt("SL % from entry price", "2.0"))
        cfg["tp_percent"] = float(self._prompt("TP % from entry price", "4.0"))

        # Break-even
        print(f"\n  {BOLD}{CYAN}── Break-Even ──{RESET}")
        cfg["breakeven_trigger_pct"] = float(self._prompt(
            "Move SL to break-even after PnL% reaches", "1.0"
        ))
        cfg["breakeven_offset_pct"] = float(self._prompt(
            "Break-even SL offset % above entry", "0.1"
        ))

        # Trailing
        print(f"\n  {BOLD}{CYAN}── Trailing Stop ──{RESET}")
        cfg["trailing_start_pct"]         = float(self._prompt("Start trailing after PnL% reaches", "2.0"))
        cfg["trailing_distance_pct"]      = float(self._prompt("Trail distance % from current price", "1.0"))
        cfg["trailing_hybrid_switch_pct"] = float(self._prompt("Hybrid switch threshold PnL%", "4.0"))

        # Save
        config_manager.save(cfg)
        print()
        _divider("─", 70, GREEN)
        print(f"  {BRIGHT_GREEN}✔  Configuration saved!{RESET}")
        _divider("─", 70, GREEN)
        time.sleep(1)

    def _prompt(self, label: str, default: str) -> str:
        default_display = f"{DIM}[{default}]{RESET}" if default else ""
        prompt_str = f"  {BRIGHT_WHITE}{label}{RESET} {default_display}: "
        val = input(prompt_str).strip()
        return val if val else default

    # ──────────────────────────────────────────────────────────────────────────
    # Config Display
    # ──────────────────────────────────────────────────────────────────────────

    def show_config(self, cfg: dict):
        from core.config_manager import BACKEND_HTTP_URL, BACKEND_WS_URL
        print(f"\n  {BOLD}{BRIGHT_CYAN}⚙  CURRENT CONFIGURATION{RESET}")
        _divider()
        secret = cfg.get("bot_secret", "")
        secret_display = secret if secret else f"{RED}NOT SET{RESET}"
        rows = [
            ("Backend HTTP",        BACKEND_HTTP_URL),
            ("Backend WebSocket",   BACKEND_WS_URL),
            ("Bot Secret",          secret_display),
            ("Mode",                cfg.get("mode", "mainnet").upper()),
            ("Collateral",          f"{cfg.get('collateral_usdc', 10)} USDC"),
            ("Leverage",            f"{cfg.get('leverage', 10)}x"),
            ("SL %",                f"{cfg.get('sl_percent', 2.0)}%"),
            ("TP %",                f"{cfg.get('tp_percent', 4.0)}%"),
            ("Break-even trigger",  f"{cfg.get('breakeven_trigger_pct', 1.0)}% PnL"),
            ("Break-even offset",   f"{cfg.get('breakeven_offset_pct', 0.1)}% above entry"),
            ("Trailing start",      f"{cfg.get('trailing_start_pct', 2.0)}% PnL"),
            ("Trailing distance",   f"{cfg.get('trailing_distance_pct', 1.0)}% from price"),
            ("Hybrid switch",       f"{cfg.get('trailing_hybrid_switch_pct', 4.0)}% PnL"),
        ]
        for label, value in rows:
            print(f"  {DIM}{label:<22}{RESET} {BRIGHT_WHITE}{value}{RESET}")
        _divider()
        input("\n  Press Enter to return to menu...")

    # ──────────────────────────────────────────────────────────────────────────
    # Bot started
    # ──────────────────────────────────────────────────────────────────────────

    def print_bot_started(self):
        print()
        _divider("═", 70, BRIGHT_GREEN)
        print(f"  {BRIGHT_GREEN}{BOLD}🚀  BOT STARTED  {RESET}{DIM}— Press Ctrl+C to stop{RESET}")
        _divider("═", 70, BRIGHT_GREEN)
        print()

    # ──────────────────────────────────────────────────────────────────────────
    # Status bar
    # ──────────────────────────────────────────────────────────────────────────

    def update_status_bar(self, positions: list, uptime: int):
        h = uptime // 3600
        m = (uptime % 3600) // 60
        s = uptime % 60
        uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
        pos_count = len(positions)
        total_pnl = sum(p.pnl_pct for p in positions)
        pnl_color = BRIGHT_GREEN if total_pnl >= 0 else BRIGHT_RED
        pnl_str = f"{'+' if total_pnl >= 0 else ''}{total_pnl:.2f}%"

        status = (
            f"  {DIM}[{RESET}{BRIGHT_CYAN}MAY9{RESET}{DIM}]{RESET}"
            f"  ⏱ {uptime_str}"
            f"  {DIM}|{RESET}  📊 Positions: {BOLD}{pos_count}{RESET}"
            f"  {DIM}|{RESET}  PnL: {pnl_color}{BOLD}{pnl_str}{RESET}"
            f"  {DIM}|{RESET}  WS: {self._ws_status_colored()}"
        )
        # Print in-place (overwrite line)
        print(f"\r{status}   ", end="", flush=True)

    def _ws_status_colored(self) -> str:
        if self._ws_status == "CONNECTED":
            return f"{BRIGHT_GREEN}●  CONNECTED{RESET}"
        elif self._ws_status == "CONNECTING":
            return f"{YELLOW}◌  CONNECTING{RESET}"
        else:
            return f"{RED}○  OFFLINE{RESET}"

    # ──────────────────────────────────────────────────────────────────────────
    # Signal display
    # ──────────────────────────────────────────────────────────────────────────

    def print_signal_received(self, signal: dict, init: bool = False):
        pair = signal.get("pair", "?")
        direction = signal.get("direction", "?").upper()
        tp = signal.get("tp") or 0
        sl = signal.get("sl") or 0
        detected = signal.get("detected_at", "")
        ts = _ts()

        dir_color = BRIGHT_GREEN if direction == "LONG" else BRIGHT_RED
        dir_icon  = "▲" if direction == "LONG" else "▼"
        label     = f"{DIM}[INIT]{RESET}" if init else f"{BRIGHT_YELLOW}[SIGNAL]{RESET}"

        print(
            f"\n  {DIM}{ts}{RESET}  {label}  "
            f"{BOLD}{BRIGHT_WHITE}{pair}{RESET}  "
            f"{dir_color}{BOLD}{dir_icon} {direction}{RESET}  "
            f"{DIM}tp={RESET}{tp:.4f}  "
            f"{DIM}sl={RESET}{sl:.4f}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Trade events
    # ──────────────────────────────────────────────────────────────────────────

    def print_trade_opened(self, pair: str, direction: str, entry: float,
                           sl: float, tp: float, collateral: float,
                           leverage: int, tx_hash: str):
        ts = _ts()
        dir_color = BRIGHT_GREEN if direction == "LONG" else BRIGHT_RED
        dir_icon  = "▲" if direction == "LONG" else "▼"
        print()
        _divider("─", 70, BRIGHT_GREEN)
        print(
            f"  {DIM}{ts}{RESET}  {BRIGHT_GREEN}✔ TRADE OPENED{RESET}  "
            f"{BOLD}{BRIGHT_WHITE}{pair}{RESET}  "
            f"{dir_color}{BOLD}{dir_icon} {direction}{RESET}  "
            f"{DIM}@ {RESET}{BOLD}{entry:,.4f}{RESET}"
        )
        print(
            f"  {DIM}SL:{RESET} {BRIGHT_RED}{sl:,.4f}{RESET}  "
            f"{DIM}TP:{RESET} {BRIGHT_GREEN}{tp:,.4f}{RESET}  "
            f"{DIM}Collateral:{RESET} {collateral} USDC  "
            f"{DIM}Leverage:{RESET} {leverage}x"
        )
        print(f"  {DIM}TX: {tx_hash[:24]}...{RESET}" if tx_hash else "")
        _divider("─", 70, BRIGHT_GREEN)

    def print_breakeven(self, pair: str, trade_index: int, sl_price: float, pnl_pct: float):
        ts = _ts()
        print(
            f"\n  {DIM}{ts}{RESET}  {BRIGHT_YELLOW}⚡ BREAK-EVEN{RESET}  "
            f"{BOLD}{pair}{RESET}  #{trade_index}  "
            f"SL → {YELLOW}{sl_price:,.4f}{RESET}  "
            f"{DIM}PnL: +{pnl_pct:.2f}%{RESET}"
        )

    def print_trail(self, pair: str, trade_index: int, sl_price: float, pnl_pct: float):
        ts = _ts()
        print(
            f"\n  {DIM}{ts}{RESET}  {BRIGHT_CYAN}↑ TRAILING SL{RESET}  "
            f"{BOLD}{pair}{RESET}  #{trade_index}  "
            f"SL → {CYAN}{sl_price:,.4f}{RESET}  "
            f"{DIM}PnL: +{pnl_pct:.2f}%{RESET}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Positions table
    # ──────────────────────────────────────────────────────────────────────────

    def show_positions_table(self, positions: list):
        print(f"\n  {BOLD}{BRIGHT_CYAN}📊  OPEN POSITIONS{RESET}")
        _divider()

        if not positions:
            print(f"  {DIM}No open positions.{RESET}")
            _divider()
            return

        # Header
        header = (
            f"  {'PAIR':<12} {'DIR':<6} {'ENTRY':>12} {'CURRENT':>12} "
            f"{'PNL%':>8} {'SL':>12} {'TP':>12} {'LEV':>5}"
        )
        print(f"{BOLD}{DIM}{header}{RESET}")
        _divider("─")

        for pos in positions:
            dir_color = BRIGHT_GREEN if pos.direction else BRIGHT_RED
            dir_str   = "LONG" if pos.direction else "SHORT"
            pnl_color = BRIGHT_GREEN if pos.pnl_pct >= 0 else BRIGHT_RED
            pnl_str   = f"{'+' if pos.pnl_pct >= 0 else ''}{pos.pnl_pct:.2f}%"

            flags = ""
            if pos.breakeven_set:
                flags += f" {YELLOW}[BE]{RESET}"
            if pos.trailing_active:
                flags += f" {CYAN}[TR]{RESET}"

            print(
                f"  {BRIGHT_WHITE}{pos.pair:<12}{RESET}"
                f" {dir_color}{dir_str:<6}{RESET}"
                f" {pos.entry_price:>12,.4f}"
                f" {pos.current_price:>12,.4f}"
                f" {pnl_color}{pnl_str:>8}{RESET}"
                f" {BRIGHT_RED}{pos.sl_price:>12,.4f}{RESET}"
                f" {BRIGHT_GREEN}{pos.tp_price:>12,.4f}{RESET}"
                f" {pos.leverage:>4}x"
                f"{flags}"
            )

        _divider()

    # ──────────────────────────────────────────────────────────────────────────
    # Trade history
    # ──────────────────────────────────────────────────────────────────────────

    def show_trade_history(self):
        from core.trade_log import TradeLog
        records = TradeLog().get_all()

        print(f"\n  {BOLD}{BRIGHT_CYAN}📋  TRADE HISTORY{RESET}")
        _divider()

        if not records:
            print(f"  {DIM}No trades recorded yet.{RESET}")
            _divider()
            input("\n  Press Enter to return to menu...")
            return

        header = (
            f"  {'#':<4} {'PAIR':<12} {'DIR':<6} {'ENTRY':>12} "
            f"{'EXIT':>12} {'PNL%':>8} {'STATUS':<10} {'OPENED':<20}"
        )
        print(f"{BOLD}{DIM}{header}{RESET}")
        _divider("─")

        for r in reversed(records[-50:]):  # Show last 50, newest first
            status = r.get("status", "OPEN")
            pnl    = r.get("pnl_pct")
            exit_p = r.get("exit_price") or 0

            status_color = BRIGHT_GREEN if status == "CLOSED" else YELLOW
            pnl_color    = BRIGHT_GREEN if (pnl or 0) >= 0 else BRIGHT_RED
            pnl_str      = f"{'+' if (pnl or 0) >= 0 else ''}{pnl:.2f}%" if pnl is not None else "—"
            dir_color    = BRIGHT_GREEN if r.get("direction") == "LONG" else BRIGHT_RED

            opened = r.get("opened_at", "")[:16].replace("T", " ")

            print(
                f"  {DIM}{r.get('id', ''):<4}{RESET}"
                f" {BRIGHT_WHITE}{r.get('pair', ''):<12}{RESET}"
                f" {dir_color}{r.get('direction', ''):<6}{RESET}"
                f" {r.get('entry_price', 0):>12,.4f}"
                f" {exit_p:>12,.4f}"
                f" {pnl_color}{pnl_str:>8}{RESET}"
                f" {status_color}{status:<10}{RESET}"
                f" {DIM}{opened:<20}{RESET}"
            )

        _divider()

        total = len(records)
        closed = [r for r in records if r.get("status") == "CLOSED" and r.get("pnl_pct") is not None]
        wins   = [r for r in closed if r.get("pnl_pct", 0) > 0]
        avg_pnl = sum(r["pnl_pct"] for r in closed) / len(closed) if closed else 0
        wr      = len(wins) / len(closed) * 100 if closed else 0

        print(f"\n  {DIM}Total trades:{RESET} {BOLD}{total}{RESET}   "
              f"{DIM}Closed:{RESET} {len(closed)}   "
              f"{DIM}Win rate:{RESET} {BRIGHT_GREEN if wr >= 50 else BRIGHT_RED}{wr:.1f}%{RESET}   "
              f"{DIM}Avg PnL:{RESET} {BRIGHT_GREEN if avg_pnl >= 0 else BRIGHT_RED}{avg_pnl:+.2f}%{RESET}")
        _divider()
        input("\n  Press Enter to return to menu...")

    # ──────────────────────────────────────────────────────────────────────────
    # WebSocket status
    # ──────────────────────────────────────────────────────────────────────────

    def print_ws_status(self, status: str, detail: str = ""):
        self._ws_status = status
        ts = _ts()
        if status == "CONNECTED":
            print(f"\n  {DIM}{ts}{RESET}  {BRIGHT_GREEN}◉  WebSocket CONNECTED{RESET}")
        elif status == "CONNECTING":
            print(f"\n  {DIM}{ts}{RESET}  {YELLOW}◌  WebSocket CONNECTING...{RESET}  {DIM}{detail}{RESET}")
        elif status == "DROPPED":
            print(f"\n  {DIM}{ts}{RESET}  {RED}○  WebSocket DROPPED{RESET}  {DIM}{detail}{RESET}")
        elif status == "CLOSED":
            print(f"\n  {DIM}{ts}{RESET}  {DIM}○  WebSocket CLOSED{RESET}")

    # ──────────────────────────────────────────────────────────────────────────
    # Generic print helpers
    # ──────────────────────────────────────────────────────────────────────────

    def print_info(self, msg: str):
        print(f"  {DIM}[{_ts()}]{RESET}  {WHITE}{msg}{RESET}")

    def print_success(self, msg: str):
        print(f"  {DIM}[{_ts()}]{RESET}  {BRIGHT_GREEN}✔  {msg}{RESET}")

    def print_warning(self, msg: str):
        print(f"  {DIM}[{_ts()}]{RESET}  {BRIGHT_YELLOW}⚠  {msg}{RESET}")

    def print_error(self, msg: str):
        print(f"  {DIM}[{_ts()}]{RESET}  {BRIGHT_RED}✖  {msg}{RESET}")