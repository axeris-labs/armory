import streamlit as st
import json
import os
import pandas as pd
import sys

# Ensure the root directory is in sys.path so imports work correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from pages.page5.utils import get_vault_info_json

# Constants
PRESET_FILE = os.path.join(os.path.dirname(__file__), "cluster_preset.json")

def load_presets():
    if not os.path.exists(PRESET_FILE):
        return []
    with open(PRESET_FILE, 'r') as f:
        return json.load(f)

def save_presets(presets):
    with open(PRESET_FILE, 'w') as f:
        json.dump(presets, f, indent=4)

def render():
    st.title("Vault Cluster Manager")

    # Load presets
    presets = load_presets()
    
    if not presets:
        st.warning("No cluster presets found.")
        return

    # Cluster Selection
    cluster_names = [p['name'] for p in presets]
    selected_cluster_name = st.selectbox("Select Cluster", cluster_names)
    
    # Find selected cluster object
    selected_cluster = next((p for p in presets if p['name'] == selected_cluster_name), None)
    
    if not selected_cluster:
        st.error("Selected cluster not found.")
        return

    # Manage Vaults
    with st.expander("Manage Vaults in Cluster"):
        # Convert dictionary to DataFrame for editing
        # Vaults structure: {"Symbol": "Address", ...}
        vaults_dict = selected_cluster.get('vaults', {})
        
        # Create list of dicts for DataFrame
        vault_data = [{"Symbol": k, "Address": v} for k, v in vaults_dict.items()]
        df = pd.DataFrame(vault_data)
        
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=f"editor_{selected_cluster_name}",
            column_config={
                "Symbol": st.column_config.TextColumn(
                    "Asset Symbol",
                    help="e.g. USDC, WETH",
                    required=True
                ),
                "Address": st.column_config.TextColumn(
                    "Vault Address",
                    help="Enter the vault address (starts with 0x)",
                    width="large",
                    required=True,
                    validate="^0x[a-fA-F0-9]{40}$"
                )
            }
        )
        
        # Reconstruct dictionary from edited DataFrame
        # Handle empty DF case
        if edited_df is not None and not edited_df.empty:
            # Filter out rows with empty keys or values
            valid_rows = edited_df[edited_df["Symbol"].astype(str).str.strip().astype(bool) & 
                                 edited_df["Address"].astype(str).str.strip().astype(bool)]
            
            # Create new dict (last occurrence wins if duplicate keys, though UI might show dupes)
            new_vaults = dict(zip(valid_rows["Symbol"].astype(str).str.strip(), 
                                valid_rows["Address"].astype(str).str.strip()))
        else:
            new_vaults = {}
            
        if new_vaults != vaults_dict:
            selected_cluster['vaults'] = new_vaults
            save_presets(presets)
            st.rerun()

    # Fetch Data Button
    if st.button("Fetch Cluster Data"):
        st.divider()
        st.subheader("Cluster Data")
        
        with st.spinner("Fetching data..."):
            all_data = []
            vaults_to_process = selected_cluster.get('vaults', {})
            progress_bar = st.progress(0)
            total_vaults = len(vaults_to_process)
            
            # Iterate over dictionary items
            for idx, (symbol, vault_addr) in enumerate(vaults_to_process.items()):
                try:
                    info = get_vault_info_json(vault_addr)
                    
                    # Flatten IRM info for better table display
                    flat_info = info.copy()
                    
                    # Inject our local symbol if needed, though get_vault_info_json returns vaultSymbol
                    # Let's keep the one from the contract, or maybe add a column "Configured Symbol"
                    flat_info["configuredSymbol"] = symbol
                    
                    irm_info = flat_info.pop('interestRateModelInfo', {})
                    for k, v in irm_info.items():
                        flat_info[f"irm_{k}"] = v
                        
                    all_data.append(flat_info)
                except Exception as e:
                    st.error(f"Error fetching {symbol} ({vault_addr}): {e}")
                
                if total_vaults > 0:
                    progress_bar.progress((idx + 1) / total_vaults)
            
            if all_data:
                df = pd.DataFrame(all_data)
                
                # Reorder columns to put important ones first
                cols = [
                    'configuredSymbol', 'vaultName', 'vaultSymbol', 'assetSymbol', 
                    'totalAssets', 'supplyCap', 
                    'currentUtilization', 'currentBorrowApy', 'currentSupplyApy',
                    'baseRateApy', 'rateAtKink'
                ]
                # Filter cols that actually exist in df
                existing_cols = [c for c in cols if c in df.columns]
                remaining_cols = [c for c in df.columns if c not in existing_cols]
                
                st.dataframe(
                    df[existing_cols + remaining_cols], 
                    use_container_width=True,
                    column_config={
                        "currentUtilization": st.column_config.NumberColumn(
                            "Util %",
                            format="%.2f %%"
                        ),
                        "currentBorrowApy": st.column_config.NumberColumn(
                            "Borrow APY",
                            format="%.2f %%"
                        ),
                        "currentSupplyApy": st.column_config.NumberColumn(
                            "Supply APY",
                            format="%.2f %%"
                        ),
                        "baseRateApy": st.column_config.NumberColumn(
                            "Base APY",
                            format="%.2f %%"
                        ),
                        "rateAtKink": st.column_config.NumberColumn(
                            "Kink APY",
                            format="%.2f %%"
                        ),
                        "totalAssets": st.column_config.NumberColumn(
                            "Total Assets",
                            format="%.2f"
                        ),
                        "supplyCap": st.column_config.NumberColumn(
                            "Supply Cap",
                            format="%.2f"
                        )
                    }
                )
            else:
                st.info("No data available.")

def main():
    render()

if __name__ == "__main__":
    main()
