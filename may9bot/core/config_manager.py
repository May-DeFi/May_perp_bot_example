import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

# ── MAY9 Backend URLs (hardcoded — not user configurable) ─────────────────────
BACKEND_HTTP_URL = "https://ostium-abcn-sdk-backend-python-ndvn.onrender.com"
BACKEND_WS_URL   = "wss://ostium-abcn-sdk-backend-python-ndvn.onrender.com/signals/ws"

DEFAULT_CONFIG = {
    "bot_secret": "",
    "mode": "mainnet",
    "collateral_usdc": 10.0,
    "leverage": 10,
    "sl_percent": 2.0,
    "tp_percent": 4.0,
    "breakeven_trigger_pct": 1.0,
    "breakeven_offset_pct": 0.1,
    "trailing_start_pct": 2.0,
    "trailing_distance_pct": 1.0,
    "trailing_hybrid_switch_pct": 4.0,
}


class ConfigManager:
    def __init__(self):
        self.path = os.path.abspath(CONFIG_FILE)

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def load(self) -> dict:
        with open(self.path, "r") as f:
            data = json.load(f)
        # Fill any missing keys with defaults
        for k, v in DEFAULT_CONFIG.items():
            if k not in data:
                data[k] = v
        return data

    def save(self, config: dict):
        with open(self.path, "w") as f:
            json.dump(config, f, indent=2)