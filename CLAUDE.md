# CLAUDE.md

## Overview

Euler Cluster Parameterization — a Streamlit tool for optimizing Euler protocol vault cluster parameters. Fetches on-chain vault state, lets users configure supply/borrow assumptions, and computes leveraged and single-sided lending strategies with heatmap sensitivity analysis.

## Commands

```bash
uv sync                          # Install dependencies
uv run streamlit run app.py      # Run the app
```

## Environment Setup

Copy `.env.example` to `.env` and set `RPC_URL` to an Ethereum mainnet RPC endpoint.

## Architecture

```
JSON presets (cluster_preset_v2.json)
        ↓
   app.py (cluster selection)
        ↓
   src/vault.py (on-chain fetch via Web3 + DeFi Llama)
        ↓
   src/utils.py (rate calculations, yield math)
        ↓
   src/strategy.py (leveraged + single-sided strategies)
        ↓
   app.py (assumptions editor, comparison tables, strategy heatmaps)
```

## Module Responsibilities

| Module | Role |
|--------|------|
| `app.py` | Streamlit entry point: cluster management, vault metrics, assumptions editor, strategy visualization, JSON export |
| `src/vault.py` | `Vault` dataclass: fetches on-chain state (balances, caps, IRM params) via Web3, DeFi Llama yield rates |
| `src/strategy.py` | `Strategy` and `SingleSidedLendingStrategy` dataclasses with yield computation and Plotly heatmaps |
| `src/utils.py` | Pure math: rate calculations, leverage, yield with LTV |
| `src/formatting.py` | Number formatters: `fmt_val`, `fmt_pct`, `fmt_tokens` |
| `src/css.py` | Custom CSS for number input button layout |

## Key Design Decisions

- **4-state model**: Current, Current@Caps, End (assumed), End@Caps — comprehensive scenario analysis
- **Session state versioning**: Editor version counter forces widget key regeneration on cluster reset
- **Cluster presets**: JSON file stores vault configurations per cluster for quick switching
- **Strategy heatmaps**: Sensitivity analysis across debt/collateral utilization ranges
