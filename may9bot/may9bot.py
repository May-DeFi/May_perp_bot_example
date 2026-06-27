"""
MAY9 Signal Bot — CLI Terminal
Connects to MAY9 backend WebSocket, receives signals, executes on Ostium via backend API.
Monitors positions with real-time prices from Ostium metadata endpoint.
"""

import asyncio
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from ui.terminal import Terminal
from core.config_manager import ConfigManager
from core.bot import Bot


async def main():
    terminal = Terminal()
    config_manager = ConfigManager()

    terminal.print_banner()

    # First launch wizard
    if not config_manager.exists():
        terminal.print_info("No configuration found. Starting setup wizard...")
        await terminal.run_setup_wizard(config_manager)

    # Main menu loop
    while True:
        choice = terminal.show_main_menu()

        if choice == "1":
            bot = Bot(config_manager.load(), terminal)
            await bot.run()

        elif choice == "2":
            terminal.show_config(config_manager.load())

        elif choice == "3":
            await terminal.run_setup_wizard(config_manager)

        elif choice == "4":
            cfg = config_manager.load()
            bot = Bot(cfg, terminal)
            await bot.show_positions()

        elif choice == "5":
            terminal.show_trade_history()

        elif choice == "6":
            terminal.print_info("Goodbye.")
            sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye.")
        sys.exit(0)
