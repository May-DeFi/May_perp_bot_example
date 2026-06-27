# MAY9 Signal Bot

On-chain copy trading terminal. Receives signals from MAY9 WebSocket and executes them on Ostium via your backend.

---

## Run from source

```cmd
pip install -r requirements.txt
python may9bot.py
```

## Build .exe (Windows)

```cmd
pip install pyinstaller
pip install -r requirements.txt
pyinstaller may9bot.spec
```

The `.exe` will be at `dist/may9bot.exe`.

Place `may9bot.exe` in any folder. On first launch it will run the setup wizard and create `config.json` and `trade_log.json` in the same folder.

---

## Files created at runtime

| File | Purpose |
|---|---|
| `config.json` | All bot settings. Edit via menu option 3 or manually. |
| `trade_log.json` | Full trade history with entry, exit, PnL. |

---

## Architecture

- **Signal source**: MAY9 backend WebSocket (`/signals/ws`)
- **Trade execution**: MAY9 backend `POST /bot/signal` with `X-Bot-Secret`
- **Price feed**: Ostium metadata endpoint (direct, no backend hop)
- **Position monitoring**: In-memory tracker refreshed via live prices every 2s
- **Pair IDs**: Fetched from `GET /bot/prices` on startup, refreshed every 10 min
- **Position recovery**: On restart, calls `POST /bot/signal action=positions` to rebuild state
