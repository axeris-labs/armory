import streamlit as st
import json
import os
from datetime import datetime, timezone

import pandas as pd

from vault import Vault
from strategy import Strategy, construct_strategies, SingleSidedLendingStrategy, construct_single_sided_strategies
from utils import calculate_rates, compute_strategy_yield

# --- Constants ---
PRESET_FILE = os.path.join(os.path.dirname(__file__), "cluster_preset_v2.json")

# --- Helper Functions ---

def load_presets():
    if not os.path.exists(PRESET_FILE):
        return []
    with open(PRESET_FILE, 'r') as f:
        return json.load(f)

def save_presets(presets):
    with open(PRESET_FILE, 'w') as f:
        json.dump(presets, f, indent=4)

def fmt_val(val):
    """Format numeric values with K/M suffixes."""
    val = float(val) if pd.notnull(val) else 0
    if val >= 1_000_000:
        return f"{val/1_000_000:.2f}M"
    elif val >= 1_000:
        return f"{val/1_000:.2f}K"
    else:
        return f"{val:,.2f}"

def _reset_cluster_state() -> None:
    """Clear session state variables related to the cluster."""
    keys_to_remove = (
        "cluster_name",
        "vault_object_map_by_input",
        "vault_object_map_by_vault",
        "vault_cfg_map_by_input",
        "onchain_df",
        "onchain_assumptions_df",
        "onchain_params_by_input",
        "assumptions_df",
        "assumptions_editor_version",
        "strategy_rows",
        "single_sided_rows",
        "borrow_rate_rows",
    )
    for k in keys_to_remove:
        st.session_state.pop(k, None)

def _build_assumptions_df(vault_object_map_by_input: dict[str, Vault]) -> pd.DataFrame:
    """Create a DataFrame for assumptions editing from vault objects."""
    rows: list[dict] = []
    for input_addr, vault in vault_object_map_by_input.items():
        irm = vault.interest_rate_model_info or {}
        rows.append(
            {
                "inputAddress": input_addr,
                "vault": vault.vault,
                "vaultSymbol": vault.vault_symbol,
                "assetSymbol": vault.asset_symbol,
                "supplyCap": vault.supply_cap,
                "borrowCap": vault.borrow_cap,
                "assumedSupply": vault.total_assets,
                "assumedBorrow": vault.total_borrowed,
                "kinkPercent": irm.get("kinkPercent"),
                "baseRateApy": irm.get("baseRateApy"),
                "rateAtKink": irm.get("rateAtKink"),
                "maximumRate": irm.get("maximumRate"),
                "nativeYield": vault.nativeYield,
            }
        )
    return pd.DataFrame(rows)


def _sync_assumptions_to_vaults(vault_object_map_by_input: dict[str, Vault]) -> None:
    """Sync assumptions_df values to vault objects and recompute derived fields."""
    assumptions_df = st.session_state.get("assumptions_df")
    if not isinstance(assumptions_df, pd.DataFrame):
        return

    for _, row in assumptions_df.iterrows():
        input_addr = str(row.get("inputAddress", "")).strip()
        vault = vault_object_map_by_input.get(input_addr)
        if not vault:
            continue

        # Update caps
        vault.supply_cap = float(row.get("supplyCap", 0) or 0)
        vault.borrow_cap = float(row.get("borrowCap", 0) or 0)

        # Update assumed supply/borrow with clamping to caps
        assumed_supply = float(row.get("assumedSupply", 0) or 0)
        assumed_borrow = float(row.get("assumedBorrow", 0) or 0)
        if vault.supply_cap > 0:
            assumed_supply = min(assumed_supply, vault.supply_cap)
        if vault.borrow_cap > 0:
            assumed_borrow = min(assumed_borrow, vault.borrow_cap)
        vault.assumed_supply = assumed_supply
        vault.assumed_borrow = assumed_borrow

        # Write clamped values back to assumptions_df
        idx = row.name
        st.session_state["assumptions_df"].at[idx, "assumedSupply"] = assumed_supply
        st.session_state["assumptions_df"].at[idx, "assumedBorrow"] = assumed_borrow

        # Update native yield
        vault.nativeYield = float(row.get("nativeYield", 0) or 0)

        # Update IRM
        irm = dict(vault.interest_rate_model_info or {})
        for key in ("kinkPercent", "baseRateApy", "rateAtKink", "maximumRate"):
            if pd.notna(row.get(key)):
                irm[key] = float(row.get(key))
        vault.interest_rate_model_info = irm
        vault.compute_derived_fields()


# --- UI Components ---

def render_vault_management(selected_cluster, presets):
    """Render the 'Manage Vaults' expander."""
    with st.expander("Manage Vaults in Cluster"):
        st.caption("Add/remove vaults and edit preset metadata (addresses + DeFiLlama mapping).")
        vaults_list = selected_cluster.get('vaults', [])

        # Prepare data for editor
        vault_data = [
            {
                "Optics": v.get("optics", ""),
                "Address": v.get("address", ""),
                "DefiLlamaPool": v.get("defillama_pool", ""),
                "Field": v.get("field", ""),
            }
            for v in vaults_list if isinstance(v, dict)
        ]
        df = pd.DataFrame(vault_data)

        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            key=f"editor_{selected_cluster.get('name')}",
            column_config={
                "Optics": st.column_config.TextColumn("Optics", help="e.g. USDC, WETH", required=True),
                "Address": st.column_config.TextColumn("Vault Address", help="Enter the vault address (starts with 0x)", width="large", required=True, validate="^0x[a-fA-F0-9]{40}$"),
                "DefiLlamaPool": st.column_config.TextColumn("DefiLlama Pool ID", help="UUID from yields.llama.fi (optional)", required=False, width="large"),
                "Field": st.column_config.TextColumn("Field", help="e.g. apyReward, apy, apyBase (optional)", required=False),
            }
        )

        # Save changes if any
        if edited_df is not None and not edited_df.empty:
            valid_rows = edited_df[edited_df["Optics"].astype(str).str.strip().astype(bool) &
                                 edited_df["Address"].astype(str).str.strip().astype(bool)]

            new_vaults = []
            for _, row in valid_rows.iterrows():
                new_vaults.append({
                    "optics": str(row.get("Optics", "")).strip(),
                    "address": str(row.get("Address", "")).strip(),
                    "defillama_pool": str(row.get("DefiLlamaPool", "")).strip(),
                    "field": str(row.get("Field", "")).strip(),
                })
        else:
            new_vaults = []

        if new_vaults != vaults_list:
            selected_cluster['vaults'] = new_vaults
            save_presets(presets)
            st.rerun()

def fetch_and_store_data(selected_cluster):
    """Fetch data from chain/DeFiLlama and update session state."""
    with st.spinner("Fetching data..."):
        all_data = []
        vault_object_map_by_input: dict[str, Vault] = {}
        vault_object_map_by_vault: dict[str, Vault] = {}
        vault_cfg_map_by_input: dict[str, dict] = {}

        vaults_to_process = selected_cluster.get('vaults', [])
        progress_bar = st.progress(0)
        total_vaults = len(vaults_to_process)

        for idx, vault_cfg in enumerate(vaults_to_process):
            try:
                symbol = vault_cfg.get("optics", "")
                vault_addr = vault_cfg.get("address", "")

                vault = Vault(
                    vault_addr,
                    defillama_pool=vault_cfg.get("defillama_pool", ""),
                    defillama_field=vault_cfg.get("field", ""),
                )
                vault_object_map_by_input[vault_addr] = vault
                vault_cfg_map_by_input[vault_addr] = dict(vault_cfg) if isinstance(vault_cfg, dict) else {}

                if vault.vault or vault_addr:
                    vault_object_map_by_vault[vault.vault or vault_addr] = vault

                # Build row data
                row = {
                    "configuredSymbol": symbol,
                    "inputAddress": vault_addr,
                    "timestamp": vault.timestamp,
                    "vault": vault.vault,
                    "vaultName": vault.vault_name,
                    "vaultSymbol": vault.vault_symbol,
                    "assetSymbol": vault.asset_symbol,
                    "totalCash": vault.total_cash,
                    "totalBorrowed": vault.total_borrowed,
                    "totalAssets": vault.total_assets,
                    "supplyCap": vault.supply_cap,
                    "borrowCap": vault.borrow_cap,
                    "currentUtilization": vault.current_utilization,
                    "currentBorrowApy": vault.current_borrow_apy,
                    "currentSupplyApy": vault.current_supply_apy,
                    "nativeYield": vault.nativeYield,
                }
                # Flatten IRM info
                for k, v in vault.interest_rate_model_info.items():
                    row[f"irm_{k}"] = v
                all_data.append(row)

            except Exception as e:
                st.error(f"Error fetching {symbol} ({vault_addr}): {e}")

            if total_vaults > 0:
                progress_bar.progress((idx + 1) / total_vaults)

        # Update Session State
        st.session_state["vault_object_map_by_input"] = vault_object_map_by_input
        st.session_state["vault_object_map_by_vault"] = vault_object_map_by_vault
        st.session_state["vault_cfg_map_by_input"] = vault_cfg_map_by_input
        st.session_state["onchain_df"] = pd.DataFrame(all_data) if all_data else pd.DataFrame()

        # Initialize Assumptions
        onchain_assumptions_df = _build_assumptions_df(vault_object_map_by_input)
        st.session_state["onchain_assumptions_df"] = onchain_assumptions_df
        st.session_state["assumptions_df"] = onchain_assumptions_df.copy()
        st.session_state["assumptions_editor_version"] = int(st.session_state.get("assumptions_editor_version", 0) or 0) + 1

        # Store immutable on-chain snapshot (source of truth for states 1a and 1b)
        st.session_state["onchain_params_by_input"] = {
            input_addr: {
                "supply_cap": v.supply_cap,
                "borrow_cap": v.borrow_cap,
                "irm": dict(v.interest_rate_model_info or {}),
                "total_assets": v.total_assets,
                "total_borrowed": v.total_borrowed,
                "native_yield": v.nativeYield,
                "current_utilization": v.current_utilization,
                "utilization_at_caps": v.utilization_at_caps,
                "current_borrow_apy": v.current_borrow_apy,
                "current_supply_apy": v.current_supply_apy,
                "caps_borrow_apy": v.caps_borrow_apy,
                "caps_supply_apy": v.caps_supply_apy,
            }
            for input_addr, v in vault_object_map_by_input.items()
        }
        st.session_state.pop("strategy_rows", None)
        st.session_state.pop("single_sided_rows", None)
        st.session_state.pop("borrow_rate_rows", None)

def render_vault_metrics(onchain_df):
    """Render the Vault Metrics table."""
    st.divider()
    st.subheader("Vault Metrics")
    st.caption("Combined on-chain values with utilization visualization.")

    # Filter and Copy
    base_cols = [
        'assetSymbol', 'totalAssets', 'totalBorrowed',
        'currentUtilization', 'currentBorrowApy', 'currentSupplyApy',
        'nativeYield', 'supplyCap', 'borrowCap'
    ]
    available_cols = [c for c in base_cols if c in onchain_df.columns]
    dashboard_df = onchain_df[available_cols].copy()

    # Numeric conversion
    numeric_cols = ['totalAssets', 'supplyCap', 'totalBorrowed', 'borrowCap', 'currentUtilization']
    for col in numeric_cols:
        if col in dashboard_df.columns:
            dashboard_df[col] = pd.to_numeric(dashboard_df[col], errors='coerce').fillna(0)

    # Calculate Derived Columns
    if 'totalAssets' in dashboard_df.columns and 'supplyCap' in dashboard_df.columns:
        dashboard_df['supplyFill'] = dashboard_df.apply(
            lambda x: (x['totalAssets'] / x['supplyCap'] * 100) if x['supplyCap'] > 0 else 0, axis=1
        )
        dashboard_df['totalAssets_display'] = dashboard_df.apply(
            lambda x: f"{fmt_val(x['totalAssets'])} / {fmt_val(x['supplyCap'])}", axis=1
        )

    if 'totalBorrowed' in dashboard_df.columns and 'borrowCap' in dashboard_df.columns:
        dashboard_df['borrowFill'] = dashboard_df.apply(
            lambda x: (x['totalBorrowed'] / x['borrowCap'] * 100) if x['borrowCap'] > 0 else 0, axis=1
        )
        dashboard_df['totalBorrowed_display'] = dashboard_df.apply(
            lambda x: f"{fmt_val(x['totalBorrowed'])} / {fmt_val(x['borrowCap'])}", axis=1
        )

    # Display Columns
    final_cols = [
        'assetSymbol',
        'totalAssets_display', 'supplyFill',
        'totalBorrowed_display', 'borrowFill',
        'currentUtilization',
        'currentBorrowApy', 'currentSupplyApy', 'nativeYield'
    ]
    final_df = dashboard_df[[c for c in final_cols if c in dashboard_df.columns]].copy()

    # Styler
    styler = final_df.style
    styler.format({
        "currentBorrowApy": "{:.2f} %",
        "currentSupplyApy": "{:.2f} %",
        "nativeYield": "{:.2f} %",
    }, na_rep="-")

    st.dataframe(
        styler,
        width="stretch",
        column_config={
            "assetSymbol": st.column_config.TextColumn("Asset"),
            "totalAssets_display": st.column_config.TextColumn("Total Assets (Value / Cap)"),
            "supplyFill": st.column_config.ProgressColumn("Supply Fill %", format="%.1f %%", min_value=0, max_value=100),
            "totalBorrowed_display": st.column_config.TextColumn("Total Borrowed (Value / Cap)"),
            "borrowFill": st.column_config.ProgressColumn("Borrow Fill %", format="%.1f %%", min_value=0, max_value=100),
            "currentUtilization": st.column_config.ProgressColumn("Util %", format="%.1f %%", min_value=0, max_value=100),
            "currentBorrowApy": st.column_config.NumberColumn("Borrow APY"),
            "currentSupplyApy": st.column_config.NumberColumn("Supply APY"),
            "nativeYield": st.column_config.NumberColumn("Native Yield"),
        }
    )

def render_assumptions_editor(selected_cluster_name, vault_object_map_by_input):
    """Render the Assumptions editor."""
    st.divider()
    st.subheader("Assumptions", help="Edit caps, assumed supply/borrow, and IRM parameters. Changes are reflected dynamically in strategies below.")

    # Ensure state exists
    assumptions_base_df = st.session_state.get("onchain_assumptions_df")
    if not isinstance(assumptions_base_df, pd.DataFrame):
        assumptions_base_df = _build_assumptions_df(vault_object_map_by_input)
        st.session_state["onchain_assumptions_df"] = assumptions_base_df

    if "assumptions_df" not in st.session_state:
        st.session_state["assumptions_df"] = assumptions_base_df.copy()

    # Ensure new columns exist (migration for existing sessions)
    for col_name, fallback_field in [("nativeYield", "nativeYield"), ("assumedSupply", "total_assets"), ("assumedBorrow", "total_borrowed")]:
        if col_name not in st.session_state["assumptions_df"].columns:
            def _get_fallback(addr, field=fallback_field):
                v = vault_object_map_by_input.get(str(addr))
                if v is None:
                    return 0.0
                return getattr(v, field, 0.0)
            st.session_state["assumptions_df"][col_name] = st.session_state["assumptions_df"]["inputAddress"].apply(_get_fallback)

    # Get current version for key generation
    version = st.session_state.get("assumptions_editor_version", 0)

    # Helper to update session state
    def update_assumption(idx, col, key):
        val = st.session_state[key]
        st.session_state["assumptions_df"].at[idx, col] = val

    # Column layout: Vault | Supply Cap | Borrow Cap | Assumed Supply | Assumed Borrow | Util % | Kink % | Base % | Kink Rate % | Max % | Native %
    col_ratios = [1, 1.3, 1.3, 1.3, 1.3, 0.9, 1, 1, 1, 1, 1]
    headers = [
        "Vault", "Supply Cap", "Borrow Cap", "Assumed Supply", "Assumed Borrow",
        "Util %", "Kink Util %", "Base Rate %", "Kink Rate %", "Max Rate %", "Native %"
    ]

    h_cols = st.columns(col_ratios, gap="small")
    for c, h in zip(h_cols, headers):
        c.markdown(f"**{h}**")

    st.markdown("<hr style='margin: 2px 0px 5px 0px; padding: 0px;'>", unsafe_allow_html=True)

    for idx, row in st.session_state["assumptions_df"].iterrows():
        cols = st.columns(col_ratios, gap="small")

        # Original Values (for tooltip)
        orig_supply_cap = assumptions_base_df.at[idx, "supplyCap"] if idx in assumptions_base_df.index else 0
        orig_borrow_cap = assumptions_base_df.at[idx, "borrowCap"] if idx in assumptions_base_df.index else 0
        orig_assumed_supply = assumptions_base_df.at[idx, "assumedSupply"] if idx in assumptions_base_df.index else 0
        orig_assumed_borrow = assumptions_base_df.at[idx, "assumedBorrow"] if idx in assumptions_base_df.index else 0
        orig_kink = assumptions_base_df.at[idx, "kinkPercent"] if idx in assumptions_base_df.index else 0
        orig_base = assumptions_base_df.at[idx, "baseRateApy"] if idx in assumptions_base_df.index else 0
        orig_kink_rate = assumptions_base_df.at[idx, "rateAtKink"] if idx in assumptions_base_df.index else 0
        orig_max = assumptions_base_df.at[idx, "maximumRate"] if idx in assumptions_base_df.index else 0
        orig_native = assumptions_base_df.at[idx, "nativeYield"] if idx in assumptions_base_df.index else 0

        # Current cap values for clamping assumed supply/borrow
        current_supply_cap = float(row['supplyCap'] or 0)
        current_borrow_cap = float(row['borrowCap'] or 0)

        # 1. Vault Name
        with cols[0]:
            st.write(f"**{row['vaultSymbol']}**")

        # 2. Supply Cap
        with cols[1]:
            key_supply_cap = f"input_supplyCap_{idx}_v{version}"
            st.number_input(
                "Supply Cap",
                value=float(row['supplyCap']),
                key=key_supply_cap,
                on_change=update_assumption,
                args=(idx, "supplyCap", key_supply_cap),
                step=1_000_000.0,
                format="%.0f",
                label_visibility="collapsed",
                help=f"On-chain: {fmt_val(orig_supply_cap)}"
            )

        # 3. Borrow Cap
        with cols[2]:
            key_borrow_cap = f"input_borrowCap_{idx}_v{version}"
            st.number_input(
                "Borrow Cap",
                value=float(row['borrowCap']),
                key=key_borrow_cap,
                on_change=update_assumption,
                args=(idx, "borrowCap", key_borrow_cap),
                step=1_000_000.0,
                format="%.0f",
                label_visibility="collapsed",
                help=f"On-chain: {fmt_val(orig_borrow_cap)}"
            )

        # 4. Assumed Supply (clamped by supply cap)
        with cols[3]:
            key_assumed_supply = f"input_assumedSupply_{idx}_v{version}"
            assumed_supply_val = float(row.get('assumedSupply', 0) or 0)
            # Clamp to cap
            if current_supply_cap > 0:
                assumed_supply_val = min(assumed_supply_val, current_supply_cap)
            st.number_input(
                "Assumed Supply",
                value=assumed_supply_val,
                key=key_assumed_supply,
                on_change=update_assumption,
                args=(idx, "assumedSupply", key_assumed_supply),
                step=1_000_000.0,
                format="%.0f",
                max_value=current_supply_cap if current_supply_cap > 0 else None,
                min_value=0.0,
                label_visibility="collapsed",
                help=f"On-chain: {fmt_val(orig_assumed_supply)}"
            )

        # 5. Assumed Borrow (clamped by borrow cap)
        with cols[4]:
            key_assumed_borrow = f"input_assumedBorrow_{idx}_v{version}"
            assumed_borrow_val = float(row.get('assumedBorrow', 0) or 0)
            # Clamp to cap
            if current_borrow_cap > 0:
                assumed_borrow_val = min(assumed_borrow_val, current_borrow_cap)
            st.number_input(
                "Assumed Borrow",
                value=assumed_borrow_val,
                key=key_assumed_borrow,
                on_change=update_assumption,
                args=(idx, "assumedBorrow", key_assumed_borrow),
                step=1_000_000.0,
                format="%.0f",
                max_value=current_borrow_cap if current_borrow_cap > 0 else None,
                min_value=0.0,
                label_visibility="collapsed",
                help=f"On-chain: {fmt_val(orig_assumed_borrow)}"
            )

        # 6. Util % (end utilization = assumed_borrow / assumed_supply)
        with cols[5]:
            end_util = (assumed_borrow_val / assumed_supply_val * 100) if assumed_supply_val > 0 else 0
            st.markdown(f"<div style='padding-top: 5px;'>{end_util:.1f} %</div>", unsafe_allow_html=True)

        # Helper for rate inputs
        def rate_input(col_idx, field, orig_val, step=0.1):
            with cols[col_idx]:
                key_rate = f"input_{field}_{idx}_v{version}"
                st.number_input(
                    field,
                    value=float(row[field] or 0),
                    key=key_rate,
                    on_change=update_assumption,
                    args=(idx, field, key_rate),
                    step=step,
                    format="%.3f",
                    label_visibility="collapsed",
                    help=f"On-chain: {orig_val:.2f}%"
                )

        # 7. Kink %
        rate_input(6, "kinkPercent", orig_kink, 1.0)

        # 8. Base %
        rate_input(7, "baseRateApy", orig_base)

        # 9. Rate at Kink %
        rate_input(8, "rateAtKink", orig_kink_rate)

        # 10. Max %
        rate_input(9, "maximumRate", orig_max, 1.0)

        # 11. Native %
        rate_input(10, "nativeYield", orig_native)


def render_changes_and_reset(vault_object_map_by_input):
    """Render the Reset button."""
    col1, spacer = st.columns([3, 9])

    with col1:
        reset_clicked = st.button("Reset Assumptions to On-chain", use_container_width=True)

    if reset_clicked:
        assumptions_base_df = st.session_state.get("onchain_assumptions_df")
        st.session_state["assumptions_df"] = assumptions_base_df.copy()
        st.session_state["assumptions_editor_version"] = int(st.session_state.get("assumptions_editor_version", 0) or 0) + 1

        # Reset Vault objects to original state
        onchain_params = st.session_state.get("onchain_params_by_input", {})
        for input_addr, params in onchain_params.items():
            vault = vault_object_map_by_input.get(input_addr)
            if vault:
                vault.supply_cap = float(params.get("supply_cap", 0))
                vault.borrow_cap = float(params.get("borrow_cap", 0))
                vault.assumed_supply = float(params.get("total_assets", 0))
                vault.assumed_borrow = float(params.get("total_borrowed", 0))
                vault.nativeYield = float(params.get("native_yield", 0))
                vault.interest_rate_model_info = dict(params.get("irm", {}))
                vault.compute_derived_fields()

        st.session_state.pop("strategy_rows", None)
        st.session_state.pop("single_sided_rows", None)
        st.session_state.pop("borrow_rate_rows", None)
        st.rerun()


def render_comparison_table(vault_object_map_by_input: dict[str, Vault]):
    """Render a 4-state comparison table: current, current-at-caps, end, end-at-caps."""
    st.divider()
    with st.expander("State Comparison", expanded=False):
        st.caption("Comparing all 4 sub-states per vault: Current (on-chain), Current at Caps (on-chain caps), End (assumed), End at Caps (assumed caps).")

        onchain_params = st.session_state.get("onchain_params_by_input", {})

        rows = []
        for input_addr, vault in vault_object_map_by_input.items():
            oc = onchain_params.get(input_addr, {})
            symbol = vault.vault_symbol or vault.asset_symbol or input_addr[:10]
            oc_irm = oc.get("irm", {})
            assumed_irm = vault.interest_rate_model_info or {}

            # Metrics to display for each state
            metrics = [
                ("Supply", oc.get("total_assets", 0), oc.get("supply_cap", 0), vault.assumed_supply, vault.supply_cap),
                ("Borrow", oc.get("total_borrowed", 0), oc.get("borrow_cap", 0), vault.assumed_borrow, vault.borrow_cap),
                ("Utilization %", oc.get("current_utilization", 0), oc.get("utilization_at_caps", 0), vault.end_utilization, vault.utilization_at_caps),
                ("Borrow APY %", oc.get("current_borrow_apy", 0), oc.get("caps_borrow_apy", 0), vault.end_borrow_apy, vault.caps_borrow_apy),
                ("Supply APY %", oc.get("current_supply_apy", 0), oc.get("caps_supply_apy", 0), vault.end_supply_apy, vault.caps_supply_apy),
                ("Kink Util %", oc_irm.get("kinkPercent", 0), oc_irm.get("kinkPercent", 0), assumed_irm.get("kinkPercent", 0), assumed_irm.get("kinkPercent", 0)),
                ("Base Rate %", oc_irm.get("baseRateApy", 0), oc_irm.get("baseRateApy", 0), assumed_irm.get("baseRateApy", 0), assumed_irm.get("baseRateApy", 0)),
                ("Kink Rate %", oc_irm.get("rateAtKink", 0), oc_irm.get("rateAtKink", 0), assumed_irm.get("rateAtKink", 0), assumed_irm.get("rateAtKink", 0)),
                ("Max Rate %", oc_irm.get("maximumRate", 0), oc_irm.get("maximumRate", 0), assumed_irm.get("maximumRate", 0), assumed_irm.get("maximumRate", 0)),
                ("Native Yield %", oc.get("native_yield", 0), oc.get("native_yield", 0), vault.nativeYield, vault.nativeYield),
            ]

            for metric_name, current_val, current_caps_val, end_val, end_caps_val in metrics:
                rows.append({
                    "Vault": symbol,
                    "Metric": metric_name,
                    "Current": round(float(current_val or 0), 3),
                    "Current at Caps": round(float(current_caps_val or 0), 3),
                    "End": round(float(end_val or 0), 3),
                    "End at Caps": round(float(end_caps_val or 0), 3),
                })

        if rows:
            comp_df = pd.DataFrame(rows)

            # Format large numbers in Supply/Borrow rows
            def format_cell(val, metric):
                if metric in ("Supply", "Borrow"):
                    return fmt_val(val)
                return f"{val:.3f}"

            display_rows = []
            for _, r in comp_df.iterrows():
                m = r["Metric"]
                display_rows.append({
                    "Vault": r["Vault"],
                    "Metric": m,
                    "Current": format_cell(r["Current"], m),
                    "Current at Caps": format_cell(r["Current at Caps"], m),
                    "End": format_cell(r["End"], m),
                    "End at Caps": format_cell(r["End at Caps"], m),
                })

            display_df = pd.DataFrame(display_rows)
            st.dataframe(display_df, hide_index=True, use_container_width=True, height=min(len(display_rows) * 35 + 40, 600))


def _compute_strategies(vault_object_map_by_input, vault_object_map_by_vault):
    """Compute leveraged and single-sided strategy yields for all 4 sub-states."""
    onchain_params = st.session_state.get("onchain_params_by_input", {})

    # Build a lookup from vault address to input address for on-chain params
    vault_to_input = {}
    for input_addr, vault in vault_object_map_by_input.items():
        vault_key = vault.vault or input_addr
        vault_to_input[vault_key] = input_addr

    # --- Leveraged Strategies ---
    strategies = construct_strategies(vault_object_map_by_vault) if isinstance(vault_object_map_by_vault, dict) else []
    strategy_rows = []
    for s in strategies:
        debt_vault = vault_object_map_by_vault.get(s.get("debtAsset"))
        coll_vault = vault_object_map_by_vault.get(s.get("collateralAsset"))
        if not debt_vault or not coll_vault:
            continue

        borrow_ltv = float(s.get("borrowLTV") or 0.0)
        liquidation_ltv = float(s.get("liquidationLTV") or 0.0)

        try:
            strategy_obj = Strategy(
                debtVault=debt_vault,
                collateralVault=coll_vault,
                borrowLTV=borrow_ltv,
                liquidationLTV=liquidation_ltv,
            )

            # Get on-chain params for both vaults
            debt_oc = onchain_params.get(vault_to_input.get(s.get("debtAsset"), ""), {})
            coll_oc = onchain_params.get(vault_to_input.get(s.get("collateralAsset"), ""), {})

            # State 1a: current (on-chain rates, borrowLTV)
            current_yield = compute_strategy_yield(
                coll_supply_apy=coll_oc.get("current_supply_apy", 0),
                coll_native_yield=coll_oc.get("native_yield", 0),
                debt_borrow_apy=debt_oc.get("current_borrow_apy", 0),
                ltv=borrow_ltv,
            )

            # State 1b: current at caps (on-chain caps rates, liquidationLTV)
            current_caps_yield = compute_strategy_yield(
                coll_supply_apy=coll_oc.get("caps_supply_apy", 0),
                coll_native_yield=coll_oc.get("native_yield", 0),
                debt_borrow_apy=debt_oc.get("caps_borrow_apy", 0),
                ltv=liquidation_ltv,
            )

            # State 2a: end (assumed rates from vault objects, borrowLTV)
            end_yield = compute_strategy_yield(
                coll_supply_apy=coll_vault.end_supply_apy,
                coll_native_yield=coll_vault.nativeYield,
                debt_borrow_apy=debt_vault.end_borrow_apy,
                ltv=borrow_ltv,
            )

            # State 2b: end at caps (assumed caps rates from vault objects, liquidationLTV)
            end_caps_yield = compute_strategy_yield(
                coll_supply_apy=coll_vault.caps_supply_apy,
                coll_native_yield=coll_vault.nativeYield,
                debt_borrow_apy=debt_vault.caps_borrow_apy,
                ltv=liquidation_ltv,
            )

            strategy_rows.append({
                "strategy": strategy_obj.strategy_name,
                "debtAsset": debt_vault.asset_symbol or debt_vault.vault_symbol or debt_vault.vault_address,
                "collateralAsset": coll_vault.asset_symbol or coll_vault.vault_symbol or coll_vault.vault_address,
                "currentYield": current_yield,
                "currentCapsYield": current_caps_yield,
                "endYield": end_yield,
                "endCapsYield": end_caps_yield,
                "debtVaultKey": s.get("debtAsset"),
                "collateralVaultKey": s.get("collateralAsset"),
                "borrowLTV": borrow_ltv,
                "liquidationLTV": liquidation_ltv,
            })
        except Exception:
            continue

    # --- Single-Sided Lending Strategies ---
    single_sided_strategies = construct_single_sided_strategies(vault_object_map_by_vault) if isinstance(vault_object_map_by_vault, dict) else []
    single_sided_rows = []
    for ss in single_sided_strategies:
        lend_vault = vault_object_map_by_vault.get(ss.get("lendAsset"))
        if not lend_vault:
            continue

        try:
            ss_obj = SingleSidedLendingStrategy(lendVault=lend_vault)
            lend_oc = onchain_params.get(vault_to_input.get(ss.get("lendAsset"), ""), {})

            single_sided_rows.append({
                "strategy": ss_obj.strategy_name,
                "asset": lend_vault.asset_symbol or lend_vault.vault_symbol or lend_vault.vault_address,
                "currentYield": lend_oc.get("current_supply_apy", 0) + lend_oc.get("native_yield", 0),
                "currentCapsYield": lend_oc.get("caps_supply_apy", 0) + lend_oc.get("native_yield", 0),
                "endYield": lend_vault.end_supply_apy + lend_vault.nativeYield,
                "endCapsYield": lend_vault.caps_supply_apy + lend_vault.nativeYield,
            })
        except Exception:
            continue

    # --- Borrow Rates ---
    borrow_rate_rows = []
    for vault_key, vault_obj in (vault_object_map_by_vault.items() if isinstance(vault_object_map_by_vault, dict) else []):
        if vault_obj.borrow_cap <= 0:
            continue
        try:
            oc = onchain_params.get(vault_to_input.get(vault_key, ""), {})
            asset = vault_obj.asset_symbol or vault_obj.vault_symbol or vault_obj.vault_address
            borrow_rate_rows.append({
                "asset": asset,
                "currentRate": oc.get("current_borrow_apy", 0),
                "currentCapsRate": oc.get("caps_borrow_apy", 0),
                "endRate": vault_obj.end_borrow_apy,
                "endCapsRate": vault_obj.caps_borrow_apy,
            })
        except Exception:
            continue

    return strategy_rows, single_sided_rows, borrow_rate_rows


def render_strategies(vault_object_map_by_input, vault_object_map_by_vault):
    """Dynamically compute and render strategy tables and charts."""
    strategy_rows, single_sided_rows, borrow_rate_rows = _compute_strategies(vault_object_map_by_input, vault_object_map_by_vault)

    yield_cols = ["currentYield", "currentCapsYield", "endYield", "endCapsYield"]

    def color_yield(val):
        if not isinstance(val, (int, float)):
            return ''
        return f'color: {"green" if val >= 0 else "red"}'

    # --- Borrow Rates & Single-Sided Lending Yields (side by side) ---
    if borrow_rate_rows or single_sided_rows:
        st.divider()
        col_borrow, col_lend = st.columns(2)

        with col_borrow:
            if borrow_rate_rows:
                st.subheader("Borrow Rates")
                st.caption("Borrow APY for each borrowable vault across the 4 states.")

                rate_cols = ["currentRate", "currentCapsRate", "endRate", "endCapsRate"]
                br_df = pd.DataFrame(borrow_rate_rows)
                br_display_cols = ["asset"] + rate_cols
                br_styler = br_df[br_display_cols].style.map(color_yield, subset=rate_cols)
                br_styler.format({col: "{:.3f} %" for col in rate_cols})

                st.dataframe(
                    br_styler,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "asset": st.column_config.TextColumn("Asset"),
                        "currentRate": st.column_config.NumberColumn("Current"),
                        "currentCapsRate": st.column_config.NumberColumn("Current at Caps"),
                        "endRate": st.column_config.NumberColumn("End"),
                        "endCapsRate": st.column_config.NumberColumn("End at Caps"),
                    }
                )

        with col_lend:
            if single_sided_rows:
                st.subheader("Single-Sided Lending Yields")
                st.caption("Yield = Supply APY + Native Yield (no leverage).")

                ss_df = pd.DataFrame(single_sided_rows)
                ss_display_cols = ["asset"] + yield_cols
                ss_styler = ss_df[ss_display_cols].style.map(color_yield, subset=yield_cols)
                ss_styler.format({col: "{:.3f} %" for col in yield_cols})

                st.dataframe(
                    ss_styler,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "asset": st.column_config.TextColumn("Asset"),
                        "currentYield": st.column_config.NumberColumn("Current"),
                        "currentCapsYield": st.column_config.NumberColumn("Current at Caps"),
                        "endYield": st.column_config.NumberColumn("End"),
                        "endCapsYield": st.column_config.NumberColumn("End at Caps"),
                    }
                )

    # --- Leveraged Strategy Yields ---
    if strategy_rows:
        st.divider()
        st.subheader("Leveraged Strategy Yields")
        st.caption("Current/End use borrowLTV; Current at Caps/End at Caps use liquidationLTV.")

        df = pd.DataFrame(strategy_rows)
        display_cols = ["strategy", "debtAsset", "collateralAsset"] + yield_cols
        styler = df[display_cols].style.map(color_yield, subset=yield_cols)
        styler.format({col: "{:.3f} %" for col in yield_cols})

        st.dataframe(
            styler,
            width="stretch",
            hide_index=True,
            column_config={
                "strategy": st.column_config.TextColumn("Strategy Name"),
                "debtAsset": st.column_config.TextColumn("Debt Asset"),
                "collateralAsset": st.column_config.TextColumn("Collateral Asset"),
                "currentYield": st.column_config.NumberColumn("Current"),
                "currentCapsYield": st.column_config.NumberColumn("Current at Caps"),
                "endYield": st.column_config.NumberColumn("End"),
                "endCapsYield": st.column_config.NumberColumn("End at Caps"),
            }
        )

        # --- Strategy Analysis Charts ---
        st.divider()
        st.subheader("Strategy Analysis")
        st.caption("Visualize yield sensitivity to utilization changes.")

        selected_strategy_name = st.selectbox(
            "Select Strategy",
            [r["strategy"] for r in strategy_rows],
            key="strategy_chart_select"
        )

        if selected_strategy_name:
            selected_row = next((r for r in strategy_rows if r["strategy"] == selected_strategy_name), None)

            if selected_row:
                d_key = selected_row.get("debtVaultKey")
                c_key = selected_row.get("collateralVaultKey")

                d_vault = vault_object_map_by_vault.get(d_key)
                c_vault = vault_object_map_by_vault.get(c_key)

                if d_vault and c_vault:
                    strat = Strategy(
                        debtVault=d_vault,
                        collateralVault=c_vault,
                        borrowLTV=float(selected_row.get("borrowLTV") or 0),
                        liquidationLTV=float(selected_row.get("liquidationLTV") or 0)
                    )

                    # Get on-chain utilizations for markers
                    onchain_params = st.session_state.get("onchain_params_by_input", {})
                    vault_to_input = {}
                    for ia, v in vault_object_map_by_input.items():
                        vault_to_input[v.vault or ia] = ia
                    d_oc = onchain_params.get(vault_to_input.get(d_key, ""), {})
                    c_oc = onchain_params.get(vault_to_input.get(c_key, ""), {})

                    fig = strat.generate_simulation_chart(
                        onchain_debt_util=d_oc.get("current_utilization"),
                        onchain_coll_util=c_oc.get("current_utilization"),
                        onchain_caps_debt_util=d_oc.get("utilization_at_caps"),
                        onchain_caps_coll_util=c_oc.get("utilization_at_caps"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.divider()

                    # Two Column Layout for Sensitivity Analysis
                    col_sens1, col_sens2 = st.columns(2)

                    with col_sens1:
                        st.markdown("#### Yield vs Collateral Util")
                        fixed_debt_util = st.slider(
                            "Fixed Debt Utilization (%)",
                            min_value=0, max_value=100, value=50, step=1,
                            key="slider_fixed_debt"
                        )
                        fig_coll = strat.generate_collateral_sensitivity_chart(fixed_debt_util / 100.0)
                        st.plotly_chart(fig_coll, use_container_width=True)

                    with col_sens2:
                        st.markdown("#### Yield vs Debt Util")
                        fixed_coll_util = st.slider(
                            "Fixed Collateral Utilization (%)",
                            min_value=0, max_value=100, value=50, step=1,
                            key="slider_fixed_coll"
                        )
                        fig_debt = strat.generate_debt_sensitivity_chart(fixed_coll_util / 100.0)
                        st.plotly_chart(fig_debt, use_container_width=True)

    # Store for export
    st.session_state["strategy_rows"] = strategy_rows
    st.session_state["single_sided_rows"] = single_sided_rows
    st.session_state["borrow_rate_rows"] = borrow_rate_rows


def build_export_json(cluster_name: str, vault_object_map_by_input: dict[str, Vault]) -> dict:
    """Build the full JSON export with 4 sub-states, modifications, and strategy yields."""
    onchain_params = st.session_state.get("onchain_params_by_input", {})

    # --- Vaults section ---
    vaults_export = {}
    for input_addr, vault in vault_object_map_by_input.items():
        oc = onchain_params.get(input_addr, {})
        symbol = vault.vault_symbol or vault.asset_symbol or input_addr[:10]
        oc_irm = oc.get("irm", {})
        assumed_irm = vault.interest_rate_model_info or {}

        vaults_export[symbol] = {
            "current": {
                "supply": oc.get("total_assets", 0),
                "borrow": oc.get("total_borrowed", 0),
                "supply_cap": oc.get("supply_cap", 0),
                "borrow_cap": oc.get("borrow_cap", 0),
                "utilization_pct": round(oc.get("current_utilization", 0), 3),
                "borrow_apy_pct": round(oc.get("current_borrow_apy", 0), 3),
                "supply_apy_pct": round(oc.get("current_supply_apy", 0), 3),
                "native_yield_pct": round(oc.get("native_yield", 0), 3),
                "irm": {
                    "kink_pct": oc_irm.get("kinkPercent", 0),
                    "base_rate_pct": oc_irm.get("baseRateApy", 0),
                    "kink_rate_pct": oc_irm.get("rateAtKink", 0),
                    "max_rate_pct": oc_irm.get("maximumRate", 0),
                },
            },
            "current_at_caps": {
                "supply": oc.get("supply_cap", 0),
                "borrow": oc.get("borrow_cap", 0),
                "utilization_pct": round(oc.get("utilization_at_caps", 0), 3),
                "borrow_apy_pct": round(oc.get("caps_borrow_apy", 0), 3),
                "supply_apy_pct": round(oc.get("caps_supply_apy", 0), 3),
            },
            "end": {
                "supply": vault.assumed_supply,
                "borrow": vault.assumed_borrow,
                "supply_cap": vault.supply_cap,
                "borrow_cap": vault.borrow_cap,
                "utilization_pct": round(vault.end_utilization, 3),
                "borrow_apy_pct": round(vault.end_borrow_apy, 3),
                "supply_apy_pct": round(vault.end_supply_apy, 3),
                "native_yield_pct": round(vault.nativeYield, 3),
                "irm": {
                    "kink_pct": assumed_irm.get("kinkPercent", 0),
                    "base_rate_pct": assumed_irm.get("baseRateApy", 0),
                    "kink_rate_pct": assumed_irm.get("rateAtKink", 0),
                    "max_rate_pct": assumed_irm.get("maximumRate", 0),
                },
            },
            "end_at_caps": {
                "supply": vault.supply_cap,
                "borrow": vault.borrow_cap,
                "utilization_pct": round(vault.utilization_at_caps, 3),
                "borrow_apy_pct": round(vault.caps_borrow_apy, 3),
                "supply_apy_pct": round(vault.caps_supply_apy, 3),
            },
        }

    # --- Modifications section ---
    modifications = {}
    base_df = st.session_state.get("onchain_assumptions_df")
    current_df = st.session_state.get("assumptions_df")

    if isinstance(base_df, pd.DataFrame) and isinstance(current_df, pd.DataFrame):
        field_map = {
            "supplyCap": "supply_cap",
            "borrowCap": "borrow_cap",
            "assumedSupply": "assumed_supply",
            "assumedBorrow": "assumed_borrow",
            "kinkPercent": "kink_pct",
            "baseRateApy": "base_rate_pct",
            "rateAtKink": "kink_rate_pct",
            "maximumRate": "max_rate_pct",
            "nativeYield": "native_yield_pct",
        }

        for idx, row in current_df.iterrows():
            if idx not in base_df.index:
                continue
            base_row = base_df.loc[idx]
            symbol = row.get("vaultSymbol", "Unknown")
            vault_mods = {}

            for col, export_name in field_map.items():
                curr_val = float(row.get(col, 0) or 0)
                base_val = float(base_row.get(col, 0) or 0)
                if abs(curr_val - base_val) > 1e-6:
                    vault_mods[export_name] = {"from": round(base_val, 3), "to": round(curr_val, 3)}

            if vault_mods:
                modifications[symbol] = vault_mods

    # --- Strategies section ---
    strategy_rows = st.session_state.get("strategy_rows", [])
    single_sided_rows = st.session_state.get("single_sided_rows", [])
    borrow_rate_rows = st.session_state.get("borrow_rate_rows", [])

    leveraged_export = []
    for sr in strategy_rows:
        leveraged_export.append({
            "name": sr["strategy"],
            "debt_asset": sr["debtAsset"],
            "collateral_asset": sr["collateralAsset"],
            "borrow_ltv": round(sr.get("borrowLTV", 0), 4),
            "liquidation_ltv": round(sr.get("liquidationLTV", 0), 4),
            "yields": {
                "current": round(sr["currentYield"], 3),
                "current_at_caps": round(sr["currentCapsYield"], 3),
                "end": round(sr["endYield"], 3),
                "end_at_caps": round(sr["endCapsYield"], 3),
            },
        })

    single_sided_export = []
    for ssr in single_sided_rows:
        single_sided_export.append({
            "name": ssr["strategy"],
            "asset": ssr["asset"],
            "yields": {
                "current": round(ssr["currentYield"], 3),
                "current_at_caps": round(ssr["currentCapsYield"], 3),
                "end": round(ssr["endYield"], 3),
                "end_at_caps": round(ssr["endCapsYield"], 3),
            },
        })

    borrow_rates_export = []
    for br in borrow_rate_rows:
        borrow_rates_export.append({
            "asset": br["asset"],
            "rates": {
                "current": round(br["currentRate"], 3),
                "current_at_caps": round(br["currentCapsRate"], 3),
                "end": round(br["endRate"], 3),
                "end_at_caps": round(br["endCapsRate"], 3),
            },
        })

    return {
        "cluster": cluster_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "vaults": vaults_export,
        "modifications": modifications,
        "borrow_rates": borrow_rates_export,
        "strategies": {
            "leveraged": leveraged_export,
            "single_sided": single_sided_export,
        },
    }


def render_download_button(cluster_name: str, vault_object_map_by_input: dict[str, Vault]):
    """Render the JSON download button."""
    st.divider()
    full_export = build_export_json(cluster_name, vault_object_map_by_input)
    slug = cluster_name.lower().replace(" ", "_")
    filename = f"euler_{slug}_state.json"

    st.download_button(
        "Download Full State JSON",
        data=json.dumps(full_export, indent=2),
        file_name=filename,
        mime="application/json",
    )


# --- Main Execution Flow ---

def main():

    st.set_page_config(layout="wide")

    # Stack number input +/- buttons vertically to save horizontal space
    st.markdown("""
    <style>
    /* Stack the buttons wrapper from horizontal to vertical, reversed (+ on top, - on bottom) */
    div:has(> [data-testid="stNumberInputStepDown"]) {
        display: flex !important;
        flex-direction: column-reverse !important;
    }

    /* Make step buttons compact for vertical stacking */
    [data-testid="stNumberInputStepDown"],
    [data-testid="stNumberInputStepUp"] {
        padding: 0 4px !important;
        min-width: 20px !important;
        width: 24px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("Vault Cluster Manager")

    # 1. Initialization
    presets = load_presets()
    if not presets:
        st.warning("No cluster presets found.")
        return

    cluster_names = [p['name'] for p in presets]
    selected_cluster_name = st.selectbox("Select Cluster", cluster_names)

    if st.session_state.get("cluster_name") != selected_cluster_name:
        _reset_cluster_state()
        st.session_state["cluster_name"] = selected_cluster_name

    selected_cluster = next((p for p in presets if p['name'] == selected_cluster_name), None)
    if not selected_cluster:
        st.error("Selected cluster not found.")
        return

    # 2. Vault Management
    render_vault_management(selected_cluster, presets)

    # 3. Data Fetching
    st.caption("Fetch reads on-chain values and resets the assumptions editor to match on-chain.")
    if st.button("Fetch Cluster Data"):
        fetch_and_store_data(selected_cluster)

    # 4. Metrics, Assumptions, Strategies (Only if data exists)
    onchain_df = st.session_state.get("onchain_df")
    vault_object_map_by_input = st.session_state.get("vault_object_map_by_input")
    vault_object_map_by_vault = st.session_state.get("vault_object_map_by_vault")

    if isinstance(onchain_df, pd.DataFrame) and not onchain_df.empty:
        render_vault_metrics(onchain_df)

        if vault_object_map_by_input:
            render_assumptions_editor(selected_cluster_name, vault_object_map_by_input)

            # Sync assumptions to vault objects (dynamic computation)
            _sync_assumptions_to_vaults(vault_object_map_by_input)

            # Show Changes & Reset
            render_changes_and_reset(vault_object_map_by_input)

            # Comparison table (4 sub-states)
            render_comparison_table(vault_object_map_by_input)

            # Strategies (dynamic, always visible)
            render_strategies(vault_object_map_by_input, vault_object_map_by_vault)

            # Download
            render_download_button(selected_cluster_name, vault_object_map_by_input)

if __name__ == "__main__":
    main()
