from web3 import Web3
from hexbytes import HexBytes
from web3.datastructures import AttributeDict
import json

VAULT_LENS = '0xc3c45633e45041bf3be841f89d2cb51e2f657403'
ABI = [{"inputs":[{"internalType":"address","name":"vault","type":"address"}],"name":"getVaultInfoFull","outputs":[{"components":[{"internalType":"uint256","name":"timestamp","type":"uint256"},{"internalType":"address","name":"vault","type":"address"},{"internalType":"string","name":"vaultName","type":"string"},{"internalType":"string","name":"vaultSymbol","type":"string"},{"internalType":"uint256","name":"vaultDecimals","type":"uint256"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"string","name":"assetName","type":"string"},{"internalType":"string","name":"assetSymbol","type":"string"},{"internalType":"uint256","name":"assetDecimals","type":"uint256"},{"internalType":"address","name":"unitOfAccount","type":"address"},{"internalType":"string","name":"unitOfAccountName","type":"string"},{"internalType":"string","name":"unitOfAccountSymbol","type":"string"},{"internalType":"uint256","name":"unitOfAccountDecimals","type":"uint256"},{"internalType":"uint256","name":"totalShares","type":"uint256"},{"internalType":"uint256","name":"totalCash","type":"uint256"},{"internalType":"uint256","name":"totalBorrowed","type":"uint256"},{"internalType":"uint256","name":"totalAssets","type":"uint256"},{"internalType":"uint256","name":"accumulatedFeesShares","type":"uint256"},{"internalType":"uint256","name":"accumulatedFeesAssets","type":"uint256"},{"internalType":"address","name":"governorFeeReceiver","type":"address"},{"internalType":"address","name":"protocolFeeReceiver","type":"address"},{"internalType":"uint256","name":"protocolFeeShare","type":"uint256"},{"internalType":"uint256","name":"interestFee","type":"uint256"},{"internalType":"uint256","name":"hookedOperations","type":"uint256"},{"internalType":"uint256","name":"configFlags","type":"uint256"},{"internalType":"uint256","name":"supplyCap","type":"uint256"},{"internalType":"uint256","name":"borrowCap","type":"uint256"},{"internalType":"uint256","name":"maxLiquidationDiscount","type":"uint256"},{"internalType":"uint256","name":"liquidationCoolOffTime","type":"uint256"},{"internalType":"address","name":"dToken","type":"address"},{"internalType":"address","name":"oracle","type":"address"},{"internalType":"address","name":"interestRateModel","type":"address"},{"internalType":"address","name":"hookTarget","type":"address"},{"internalType":"address","name":"evc","type":"address"},{"internalType":"address","name":"protocolConfig","type":"address"},{"internalType":"address","name":"balanceTracker","type":"address"},{"internalType":"address","name":"permit2","type":"address"},{"internalType":"address","name":"creator","type":"address"},{"internalType":"address","name":"governorAdmin","type":"address"},{"components":[{"internalType":"bool","name":"queryFailure","type":"bool"},{"internalType":"bytes","name":"queryFailureReason","type":"bytes"},{"internalType":"address","name":"vault","type":"address"},{"internalType":"address","name":"interestRateModel","type":"address"},{"components":[{"internalType":"uint256","name":"cash","type":"uint256"},{"internalType":"uint256","name":"borrows","type":"uint256"},{"internalType":"uint256","name":"borrowSPY","type":"uint256"},{"internalType":"uint256","name":"borrowAPY","type":"uint256"},{"internalType":"uint256","name":"supplyAPY","type":"uint256"}],"internalType":"struct InterestRateInfo[]","name":"interestRateInfo","type":"tuple[]"},{"components":[{"internalType":"address","name":"interestRateModel","type":"address"},{"internalType":"enum InterestRateModelType","name":"interestRateModelType","type":"uint8"},{"internalType":"bytes","name":"interestRateModelParams","type":"bytes"}],"internalType":"struct InterestRateModelDetailedInfo","name":"interestRateModelInfo","type":"tuple"}],"internalType":"struct VaultInterestRateModelInfo","name":"irmInfo","type":"tuple"},{"components":[{"internalType":"address","name":"collateral","type":"address"},{"internalType":"uint256","name":"borrowLTV","type":"uint256"},{"internalType":"uint256","name":"liquidationLTV","type":"uint256"},{"internalType":"uint256","name":"initialLiquidationLTV","type":"uint256"},{"internalType":"uint256","name":"targetTimestamp","type":"uint256"},{"internalType":"uint256","name":"rampDuration","type":"uint256"}],"internalType":"struct LTVInfo[]","name":"collateralLTVInfo","type":"tuple[]"},{"components":[{"internalType":"bool","name":"queryFailure","type":"bool"},{"internalType":"bytes","name":"queryFailureReason","type":"bytes"},{"internalType":"uint256","name":"timestamp","type":"uint256"},{"internalType":"address","name":"oracle","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"unitOfAccount","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMid","type":"uint256"},{"internalType":"uint256","name":"amountOutBid","type":"uint256"},{"internalType":"uint256","name":"amountOutAsk","type":"uint256"}],"internalType":"struct AssetPriceInfo","name":"liabilityPriceInfo","type":"tuple"},{"components":[{"internalType":"bool","name":"queryFailure","type":"bool"},{"internalType":"bytes","name":"queryFailureReason","type":"bytes"},{"internalType":"uint256","name":"timestamp","type":"uint256"},{"internalType":"address","name":"oracle","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"unitOfAccount","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMid","type":"uint256"},{"internalType":"uint256","name":"amountOutBid","type":"uint256"},{"internalType":"uint256","name":"amountOutAsk","type":"uint256"}],"internalType":"struct AssetPriceInfo[]","name":"collateralPriceInfo","type":"tuple[]"},{"components":[{"internalType":"address","name":"oracle","type":"address"},{"internalType":"string","name":"name","type":"string"},{"internalType":"bytes","name":"oracleInfo","type":"bytes"}],"internalType":"struct OracleDetailedInfo","name":"oracleInfo","type":"tuple"},{"components":[{"internalType":"bool","name":"queryFailure","type":"bool"},{"internalType":"bytes","name":"queryFailureReason","type":"bytes"},{"internalType":"uint256","name":"timestamp","type":"uint256"},{"internalType":"address","name":"oracle","type":"address"},{"internalType":"address","name":"asset","type":"address"},{"internalType":"address","name":"unitOfAccount","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMid","type":"uint256"},{"internalType":"uint256","name":"amountOutBid","type":"uint256"},{"internalType":"uint256","name":"amountOutAsk","type":"uint256"}],"internalType":"struct AssetPriceInfo","name":"backupAssetPriceInfo","type":"tuple"},{"components":[{"internalType":"address","name":"oracle","type":"address"},{"internalType":"string","name":"name","type":"string"},{"internalType":"bytes","name":"oracleInfo","type":"bytes"}],"internalType":"struct OracleDetailedInfo","name":"backupAssetOracleInfo","type":"tuple"}],"internalType":"struct VaultInfoFull","name":"arg_0","type":"tuple"}],"stateMutability":"view","type":"function"}]
# Constants
SECONDS_PER_YEAR = 31536000
SPY_SCALE = 10**27
UINT32_MAX = 4294967295
RPC_URL = os.getenv('RPC_URL')

def fetch_vault_info(vault_address):
    """
    Fetches VaultInfoFull from the VaultLens contract for the given vault address.
    """
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.is_connected():
            raise Exception("Failed to connect to RPC")
        
        contract = w3.eth.contract(address=w3.to_checksum_address(VAULT_LENS), abi=ABI)
        
        # Ensure address is checksummed
        if not w3.is_checksum_address(vault_address):
            vault_address = w3.to_checksum_address(vault_address)
            
        data = contract.functions.getVaultInfoFull(vault_address).call()
        return data
    except Exception as e:
        print(f"Error fetching vault info: {e}")
        raise e

def decode_primitive(data):
    """
    Helper to convert Web3 primitives (HexBytes, bytes) to strings.
    """
    if isinstance(data, HexBytes):
        return data.hex()
    elif isinstance(data, bytes):
        return data.hex()
    else:
        return data

def map_to_schema(data, components):
    """
    Recursively maps tuple data to a dictionary based on the ABI components schema.
    """
    result = {}
    for i, component in enumerate(components):
        name = component['name']
        type_str = component['type']
        
        # Safety check for index
        if i >= len(data):
            break
            
        value = data[i]
        
        if type_str == 'tuple':
            result[name] = map_to_schema(value, component['components'])
        elif type_str == 'tuple[]':
            result[name] = [map_to_schema(item, component['components']) for item in value]
        else:
            result[name] = decode_primitive(value)
    return result

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
        "kinkPercent": kink_util,
        "baseRateApy": to_apy(r0),
        "rateAtKink": to_apy(r_kink),
        "maximumRate": to_apy(r_100)
    }

def to_apy(rate_per_sec):
    # APY = (1 + r)^N - 1
    # Rate is scaled by 1e27
    
    r_decimal = rate_per_sec / SPY_SCALE
    
    # We can use exp approximation or power
    # (1 + r)^N
    if r_decimal == 0:
        return 0.0
        
    apy = ((1 + r_decimal) ** SECONDS_PER_YEAR) - 1
    return apy

def calculate_rates(utilization, kink, base_rate, rate_at_kink, max_rate):
    """
    Calculates borrow and supply rates based on linear interpolation.
    Points: (0, base), (kink, rate_at_kink), (1, max_rate)
    """
    if utilization < 0:
        utilization = 0.0
    if utilization > 1:
        utilization = 1.0

    borrow_rate = 0.0
    
    if utilization <= kink:
        # Interpolate between (0, base) and (kink, rate_at_kink)
        if kink > 0:
            slope = (rate_at_kink - base_rate) / kink
            borrow_rate = base_rate + (slope * utilization)
        else:
            borrow_rate = base_rate
    else:
        # Interpolate between (kink, rate_at_kink) and (1, max_rate)
        if kink < 1:
            slope = (max_rate - rate_at_kink) / (1 - kink)
            borrow_rate = rate_at_kink + (slope * (utilization - kink))
        else:
            borrow_rate = rate_at_kink

    supply_rate = utilization * 0.9 * borrow_rate
    return borrow_rate, supply_rate

def get_vault_info_json(vault_address):
    """
    Wrapper function to fetch and return filtered and decoded JSON-ready dictionary.
    """
    raw_data = fetch_vault_info(vault_address)
    
    # Find the output schema from ABI
    fn_abi = next((x for x in ABI if x.get('name') == 'getVaultInfoFull'), None)
    
    full_data = {}
    if fn_abi and 'outputs' in fn_abi and len(fn_abi['outputs']) > 0:
        # The function returns a single struct wrapped in a tuple/list
        output_components = fn_abi['outputs'][0]['components']
        
        # Determine if raw_data is the struct itself or wrapped in a tuple/list
        data_to_map = raw_data
        if isinstance(raw_data, (list, tuple)) and len(raw_data) == 1 and isinstance(raw_data[0], (list, tuple)):
            data_to_map = raw_data[0]
            
        full_data = map_to_schema(data_to_map, output_components)
    else:
        full_data = decode_primitive(raw_data)
        
    # Filter and process data
    vault_decimals = full_data.get("vaultDecimals", 0)
    scale_factor = 10 ** vault_decimals if vault_decimals else 1

    total_cash = full_data.get("totalCash", 0) / scale_factor
    total_borrowed = full_data.get("totalBorrowed", 0) / scale_factor
    total_assets = full_data.get("totalAssets", 0) / scale_factor
    supply_cap = full_data.get("supplyCap", 0) / scale_factor
    borrow_cap = full_data.get("borrowCap", 0) / scale_factor

    filtered = {
        "timestamp": full_data.get("timestamp"),
        "vault": full_data.get("vault"),
        "vaultName": full_data.get("vaultName"),
        "vaultSymbol": full_data.get("vaultSymbol"),
        "vaultDecimals": full_data.get("vaultDecimals"),
        "asset": full_data.get("asset"),
        "assetName": full_data.get("assetName"),
        "assetSymbol": full_data.get("assetSymbol"),
        "assetDecimals": full_data.get("assetDecimals"),
        "totalCash": total_cash,
        "totalBorrowed": total_borrowed,
        "totalAssets": total_assets,
        "supplyCap": supply_cap,
        "borrowCap": borrow_cap,
        "interestRateModel": full_data.get("interestRateModel"),
        "interestRateModelInfo": {},
        "collateralLTVInfo": []
    }
    
    # Process IRM parameters
    irm_info = full_data.get("irmInfo", {}).get("interestRateModelInfo", {})
    irm_type = str(irm_info.get("interestRateModelType", ""))
    params_hex = irm_info.get("interestRateModelParams", "")
    
    # Only decode if we have params. Assuming type 1 (Kink) as per request context or just check params length.
    # The user example implies we should try to extract params.
    # In decode_vault_info.py it checks if type == "1". 
    # But here we might just want to try decoding if it looks like kink params.
    # For safety let's use the type check if available, or just try if params are long enough.
    if params_hex:
        # The user specifically mentioned type 1 in the separate file context.
        # But for robustness, if we can read the type, we use it.
        # If type is missing/unknown but we have params, we could try.
        # Let's stick to the logic from decode_vault_info.py:
        if irm_type == "1":
             filtered["interestRateModelInfo"] = decode_kink_params(params_hex)
        elif not irm_type and len(params_hex) >= 2 + 64*4: # Fallback if type is missing but params look like kink params
             filtered["interestRateModelInfo"] = decode_kink_params(params_hex)

    # Calculations for Utilization and Rates
    # Current Utilization
    current_utilization = 0.0
    if total_assets > 0:
        current_utilization = total_borrowed / total_assets
    
    # Utilization at Caps
    utilization_at_caps = 0.0
    if supply_cap > 0:
        utilization_at_caps = borrow_cap / supply_cap
    
    filtered["currentUtilization"] = current_utilization
    filtered["utilizationAtCaps"] = utilization_at_caps

    # Rate Interpolation
    irm_params = filtered.get("interestRateModelInfo", {})
    if irm_params and "kinkPercent" in irm_params:
        kink = irm_params.get("kinkPercent", 0)
        base = irm_params.get("baseRateApy", 0)
        rate_at_kink = irm_params.get("rateAtKink", 0)
        max_rate = irm_params.get("maximumRate", 0)

        # Calculate for Current Utilization
        curr_borrow_apy, curr_supply_apy = calculate_rates(current_utilization, kink, base, rate_at_kink, max_rate)
        filtered["currentBorrowApy"] = curr_borrow_apy
        filtered["currentSupplyApy"] = curr_supply_apy

        # Calculate for Utilization at Caps
        caps_borrow_apy, caps_supply_apy = calculate_rates(utilization_at_caps, kink, base, rate_at_kink, max_rate)
        filtered["capsBorrowApy"] = caps_borrow_apy
        filtered["capsSupplyApy"] = caps_supply_apy

    # Process Collateral LTV Info
    raw_ltv_info = full_data.get("collateralLTVInfo", [])
    if isinstance(raw_ltv_info, list):
        for item in raw_ltv_info:
            borrow_ltv = item.get("borrowLTV", 0) / 10000
            
            # Skip if borrowLTV is 0
            if borrow_ltv == 0:
                continue
                
            filtered["collateralLTVInfo"].append({
                "collateral": item.get("collateral"),
                "borrowLTV": borrow_ltv,
                "liquidationLTV": item.get("liquidationLTV", 0) / 10000
            })
            
    return filtered