import json
import os
import sys
import datetime
from pathlib import Path

# Constants
SECONDS_PER_YEAR = 31536000
SPY_SCALE = 10**27
UINT32_MAX = 4294967295

def main():
    script_dir = Path(__file__).parent
    data_path = script_dir / 'method_respose.json'

    if not data_path.exists():
        print(f"Error: {data_path} not found.")
        sys.exit(1)

    with open(data_path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            sys.exit(1)

    # Handle wrapped structure
    if "" in data and isinstance(data[""], dict):
        data = data[""]

    # Process and Format
    processed = process_data(data)

    # Output
    print(json.dumps(processed, indent=2))
    
    # Save to file
    with open(script_dir / 'decoded_response.json', 'w') as f:
        json.dump(processed, f, indent=2)

def process_data(data):
    # Deep copy or just modify mechanism. Modifying logic.
    
    # Format main fields
    format_token_amounts(data)
    
    # Process IRM
    if "irmInfo" in data and "interestRateModelInfo" in data["irmInfo"]:
        irm_info = data["irmInfo"]["interestRateModelInfo"]
        irm_type = str(irm_info.get("interestRateModelType", ""))
        params_hex = irm_info.get("interestRateModelParams", "")
        
        # Type 1 is KINK
        if irm_type == "1" and params_hex:
            irm_info["decodedParams"] = decode_kink_params(params_hex)

    return data

def format_token_amounts(data):
    # Vault decimals
    vault_decimals = int(data.get("vaultDecimals", 18))
    vault_symbol = data.get("vaultSymbol", "")
    
    # Asset decimals
    asset_decimals = int(data.get("assetDecimals", 18))
    asset_symbol = data.get("assetSymbol", "")
    
    # Helper to check and format
    def add_fmt(key, decimals, symbol):
        if key in data:
            data[f"{key}_formatted"] = f"{format_units(data[key], decimals)} {symbol}"

    add_fmt("totalShares", vault_decimals, vault_symbol)
    add_fmt("accumulatedFeesShares", vault_decimals, vault_symbol)
    
    add_fmt("totalAssets", asset_decimals, asset_symbol)
    add_fmt("totalCash", asset_decimals, asset_symbol)
    add_fmt("totalBorrowed", asset_decimals, asset_symbol)
    add_fmt("accumulatedFeesAssets", asset_decimals, asset_symbol)
    add_fmt("supplyCap", asset_decimals, asset_symbol)
    add_fmt("borrowCap", asset_decimals, asset_symbol)
    
    # Timestamps
    if "timestamp" in data and data["timestamp"]:
        try:
            ts = int(data["timestamp"])
            if ts > 0:
                dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()
                data["timestamp"] = f"{ts} ({dt})"
        except:
            pass
            
    # Recursive check for timestamps in sub-objects if needed, but main one is handled.
    if "collateralLTVInfo" in data and isinstance(data["collateralLTVInfo"], list):
        for item in data["collateralLTVInfo"]:
            if "targetTimestamp" in item:
                 try:
                    ts = int(item["targetTimestamp"])
                    if ts > 0:
                        dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()
                        item["targetTimestamp"] = f"{ts} ({dt})"
                 except: pass

def decode_kink_params(hex_str):
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]
        
    if len(hex_str) < 64 * 4:
        return {"error": "Insufficient params length"}
        
    chunks = [int(hex_str[i*64 : (i+1)*64], 16) for i in range(4)]
    
    base_rate_raw = chunks[0]
    slope1_raw = chunks[1]
    slope2_raw = chunks[2]
    kink_raw = chunks[3]
    
    # Calculate Rates at specific points
    # IRMLinearKink.sol: ir = base + (util * slope)
    # where util is 0..type(uint32).max
    
    r0 = base_rate_raw
    r_kink = base_rate_raw + (slope1_raw * kink_raw)
    
    # At 100% (UINT32_MAX)
    # ir = base + (kink * slope1) + (slope2 * (UINT32_MAX - kink))
    r_100 = r_kink + (slope2_raw * (UINT32_MAX - kink_raw))
    
    kink_util = kink_raw / UINT32_MAX

    return {
        "raw": {
            "baseRate": str(base_rate_raw),
            "slope1": str(slope1_raw),
            "slope2": str(slope2_raw),
            "kink": str(kink_raw)
        },
        "formatted": {
            "kink_percent": f"{kink_util * 100:.2f}%",
            "base_rate_apy": to_apy(r0),
            "rate_at_0_util_apy": to_apy(r0),
            "rate_at_kink_apy": to_apy(r_kink),
            "rate_at_100_util_apy": to_apy(r_100)
    # Slopes themselves aren't rates, so displaying them as APY is misleading. 
    # Better to show the rates at key points.
        }
    }

def to_apy(rate_per_sec):
    # APY = (1 + r)^N - 1
    # Rate is scaled by 1e27
    
    r_decimal = rate_per_sec / SPY_SCALE
    
    # We can use exp approximation or power
    # (1 + r)^N
    if r_decimal == 0:
        return "0.00%"
        
    apy = ((1 + r_decimal) ** SECONDS_PER_YEAR) - 1
    return f"{apy * 100:.2f}%"

def format_units(value, decimals):
    s = str(value)
    if not s or s == "0":
        return "0"
        
    if len(s) <= decimals:
        padded = s.zfill(decimals + 1)
        whole = "0"
        frac = padded
    else:
        whole = s[:-decimals]
        frac = s[-decimals:]
    
    # Trim trailing zeros in frac
    frac = frac.rstrip('0')
    if not frac:
        return whole
    return f"{whole}.{frac}"

if __name__ == "__main__":
    main()
