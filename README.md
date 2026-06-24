# MAY9

**Professional perpetuals trading, live copy-trading signals, and autonomous on-chain yield — one wallet, one platform.**

MAY9 is a non-custodial DeFi platform built on Base and Arbitrum. Three independent products, one connected experience.

---

## 🧭 Platform Overview

### 01 · Trade — Perpetuals Terminal

A low-latency terminal for trading perpetual futures across 120+ markets — crypto, forex, equities, commodities and indices. Long/short with up to 200x leverage, market and limit orders, TradingView charts, and delegated execution so you never expose your main wallet. Available in Demo and Live mode from the same interface.

### 02 · Signals — Live Copy-Trading Feed

A continuous real-time feed of structured trade ideas across all supported markets. Every signal carries a pair, direction, entry, stop-loss, and targets — issued the moment the opportunity is identified. Track live PnL per signal, view the leaderboard, and copy directly into the terminal in one click. Auto-Copy mode executes signals automatically when enabled.

The **Bot API** (this repository) gives programmatic access to the same signal feed so developers and algorithmic traders can build their own execution layer on top.

### 03 · Yield — Autonomous DEX Liquidity

Deposit USDC and earn passive yield from real swap fees on Uniswap V4 Base. A hook contract monitors every swap, detects price drift and ratio imbalance, and repositions the active range automatically. The StrategyManager continuously evaluates pool candidates and migrates capital when a significantly better opportunity is detected. Each pool has its own isolated vault — your risk never mixes with other depositors.

---

## 🤖 Bot API — Getting Started

The Bot API gives you programmatic access to the MAY9 signal feed. You can use it to receive signals in real time, build custom execution logic, automate your strategy, or integrate MAY9 signals into your own systems.

Full code examples for REST and WebSocket in JavaScript and Python are in the `/examples` folder of this repository.

### Step 1 — Connect your wallet

Visit [app.may9.io](https://may9.netlify.app) and connect your wallet using the **Connect Wallet** button in the top right corner of the terminal.

> Signals are wallet-gated. You must connect a wallet before you can generate a Bot API key.

![MAY9 terminal — connect wallet and open settings](./images/terminal-settings.jpeg)

---

### Step 2 — Generate your Bot API key

Once your wallet is connected, click the **⚙️ Settings icon** in the top navigation bar, next to the DEMO / LIVE toggle.

The **External Bot Keys** modal will open.

![External Bot Keys modal — generate your key](./images/bot-keys-modal.jpeg)

1. The key name is pre-filled as `auto-copy`
2. Click **GENERATE**
3. Copy your key immediately — it will not be shown again

You can generate multiple keys for different bots or strategies. Each key is tied to your connected wallet address.

---

### Step 3 — Authenticate and start receiving signals

Pass your key in the `Authorization: Bearer` header on every API request. Full endpoint reference, payload schema, and code examples are in the `/docs` and `/examples` folders of this repository.

---

## 📋 Signal Payload

Every signal delivered via REST or WebSocket contains the same structured fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique signal identifier |
| `pair` | string | Trading pair e.g. `EUR/USD`, `BTC/USD` |
| `direction` | `long` / `short` | Trade direction |
| `entry` | number | Suggested entry price at signal issuance |
| `stop` | number | Stop-loss level |
| `targets` | number[] | Take-profit levels in order |
| `leverage` | number | Suggested leverage |
| `status` | `active` / `closed` / `cancelled` | Current signal state |
| `pnl_pct` | number | Live PnL percentage from entry |
| `issued_at` | ISO 8601 | Timestamp signal was issued |
| `closed_at` | ISO 8601 / null | Timestamp closed, null if still active |
| `issuer` | string | Signal source identifier |

---

## ✅ What is guaranteed

- **Signal structure** — every signal will always contain the fields above. The schema will not change without a versioned API update and advance notice.
- **Real-time delivery** — signals are pushed as issued, without delay on the platform side.
- **Key persistence** — your API key remains valid until you revoke it from the settings modal.
- **Yield mechanics** — the hook contract behavior (drift detection, range repositioning, migration logic) is fully on-chain and verifiable on Basescan. It behaves exactly as the contract specifies.
- **Non-custodial** — MAY9 never holds your funds. Every position and deposit is wallet-native.

---

## ❌ What is NOT guaranteed

- **Signal performance** — past win rates and PnL figures are historical records, not a guarantee of future results. Signals can and do result in losses. Never risk capital you cannot afford to lose.
- **Entry availability** — signals are issued in real time. By the time your bot receives and executes a signal, the entry price may have moved. Execution slippage is your responsibility.
- **Yield APY** — figures shown are trailing averages based on recent pool activity, not fixed rates. APY varies with pool trading volume, market conditions, and active price range. It can be significantly lower or temporarily zero during low-volume periods.
- **Pool migration accuracy** — the StrategyManager is autonomous but not infallible. It acts on vol/liq ratio data and may not always migrate at the optimal moment.
- **Token price** — if your yield pool contains a non-stablecoin asset, that side of your position carries market price risk independent of yield earned.
- **Uptime** — MAY9 is an early-stage protocol. Downtime, maintenance windows, and API changes may occur. Watch this repository and our X account for updates.

---

## ⚠️ Risk Disclosure

Trading perpetual futures involves significant risk of loss. Leverage amplifies both gains and losses. Use Demo mode before trading with real funds.

Providing liquidity in concentrated ranges carries impermanent loss risk. The more volatile the token pair, the higher the IL risk relative to fees earned.

Smart contracts carry inherent risk regardless of audits. MAY9's contracts are deployed live and have been reviewed, but no audit eliminates all risk. Only deposit what you can afford to lose.

Nothing on this platform or in this repository constitutes financial advice.

---

## 🔗 Links

| | |
|--|--|
| Platform | [app.may9.io](https://may9.netlify.app) |
| Terminal | [app.may9.io/terminal](https://may9.netlify.app/terminal) |
| Yield | [app.may9.io/yield](https://may9.netlify.app/yield) |
| X / Twitter | [@may9io]() |
| Contract (Base) | verify on Basescan |

---

## 📁 Repository Structure

```
/docs          API reference and endpoint documentation
/examples      Code examples — REST and WebSocket in JS and Python
/LICENSE
/README.md
```

---

*MAY9 © 2026 · Non-custodial · Built on Base and arbitrium*
