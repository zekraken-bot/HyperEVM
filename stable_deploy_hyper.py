from web3 import Web3
import json
import os
from dotenv import load_dotenv
from decimal import Decimal
import requests

load_dotenv()

def fp(number):
    return int(Decimal(number) * Decimal(10**18))

# Setup web3 connection
def setup_web3(rpc_url, private_key):
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise Exception(f"Failed to connect to RPC: {rpc_url}")
    
    print(f"Connected to network with chain ID: {w3.eth.chain_id}")
    account = w3.eth.account.from_key(private_key)
    print(f"Using account: {account.address}")
    return w3, account

# Function to set big block flag via HyperCore
def set_big_block_flag(account_address, private_key):
    """
    Set the HyperCore user flag to use big blocks
    """
    try:
        # HyperCore API endpoint
        hypercore_url = "https://api.hyperliquid.xyz/exchange"
        
        # Create the action to enable big blocks
        action = {
            "type": "evmUserModify",
            "usingBigBlocks": True
        }
        
        # Create timestamp (in milliseconds)
        import time
        timestamp = int(time.time() * 1000)
        
        # Create the request payload
        payload = {
            "action": action,
            "nonce": timestamp,
            "signature": None  # Will be filled by signing
        }
        
        # Note: You'll need to implement proper signing for HyperCore
        # This is a placeholder - actual implementation requires HyperCore signing
        print(f"Setting big block flag for address: {account_address}")
        print(f"Action: {action}")
        print("Note: You may need to set this flag manually via HyperCore interface")
        print("or implement proper HyperCore signing in this script.")
        
        return True
        
    except Exception as e:
        print(f"Failed to set big block flag: {e}")
        print("You may need to set this manually via HyperCore interface")
        return False

# Function to get big block gas price for Hyperliquid
def get_big_block_gas_price(w3):
    try:
        # Use custom RPC method for big block gas price
        big_block_gas_price = w3.manager.request_blocking("eth_bigBlockGasPrice", [])
        print(f"Big block gas price: {int(big_block_gas_price, 16)}")
        return int(big_block_gas_price, 16)
    except Exception as e:
        print(f"Failed to get big block gas price: {e}")
        # Fallback to regular gas price * multiplier
        regular_price = w3.eth.gas_price
        fallback_price = int(regular_price * 3)
        print(f"Using fallback big block gas price: {fallback_price}")
        return fallback_price

# Function to deploy a stable pool (always using big blocks)
def deploy_stable_pool(
    w3, 
    account,
    factory_address, 
    pool_name, 
    pool_symbol,
    token_addresses,
    amplification_parameter,
    pause_manager,
    swap_fee_manager,
    pool_creator,
    swap_fee_percentage,
    pool_hooks_contract,
    enable_donation,
    disable_unbalanced_liquidity,
    salt
):
    # Load the factory ABI (save the stable pool ABI as stable_factory_abi.json)
    with open("stable_factory_abi.json", "r") as f:
        factory_abi = json.load(f)
    
    # Create contract instance
    factory_address = w3.to_checksum_address(factory_address)
    factory = w3.eth.contract(address=factory_address, abi=factory_abi)
    
    # Prepare token config
    token_config = []
    for token in token_addresses:
        token_config.append({
            'token': w3.to_checksum_address(token),
            'tokenType': 0,  # STANDARD token type
            'rateProvider': '0x0000000000000000000000000000000000000000',
            'paysYieldFees': False
        })
    
    # Sort tokens alphabetically by address
    token_config = sorted(token_config, key=lambda x: x['token'].lower())
    
    # Prepare roles config
    roles_config = {
        'pauseManager': pause_manager,
        'swapFeeManager': swap_fee_manager,
        'poolCreator': pool_creator
    }
    
    # Convert pool hooks contract address
    pool_hooks_contract = w3.to_checksum_address(pool_hooks_contract)
    
    # Always use big block settings
    print("🔥 ALWAYS USING BIG BLOCK SETTINGS 🔥")
    
    # Estimate gas for the transaction
    try:
        gas_estimate = factory.functions.create(
            pool_name,
            pool_symbol,
            token_config,
            amplification_parameter,
            roles_config,
            swap_fee_percentage,
            pool_hooks_contract,
            enable_donation,
            disable_unbalanced_liquidity,
            salt
        ).estimate_gas({'from': account.address})

        gas_limit = int(gas_estimate * 1.5)  # Higher buffer for big blocks
        print(f"Estimated gas: {gas_estimate}, using gas limit: {gas_limit}")
    except Exception as e:
        print(f"Gas estimation failed: {str(e)}")
        gas_limit = 15000000  # Very high fallback for big blocks
        print(f"Using fallback gas limit: {gas_limit}")
    
    # Always use big block gas pricing with legacy transaction format
    print("Using big block gas pricing with legacy format...")
    base_gas_price = get_big_block_gas_price(w3)
    
    # Use legacy transaction format for better big block compatibility
    tx_params = {
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': gas_limit,
        'gasPrice': base_gas_price,  # Legacy format
    }
    
    print(f"Gas price: {base_gas_price}")
    print(f"Transaction params: {tx_params}")
    
    # Build transaction
    tx = factory.functions.create(
        pool_name,
        pool_symbol,
        token_config,
        amplification_parameter,
        roles_config,
        swap_fee_percentage,
        pool_hooks_contract,
        enable_donation,
        disable_unbalanced_liquidity,
        salt
    ).build_transaction(tx_params)

    print("\n🚀 BIG BLOCK STABLE POOL DEPLOYMENT PARAMETERS:")
    print(f"Pool Name: {pool_name}")
    print(f"Pool Symbol: {pool_symbol}")
    print(f"Token Config: {token_config}")
    print(f"Amplification Parameter: {amplification_parameter}")
    print(f"Roles Config: {roles_config}")
    print(f"Swap Fee Percentage: {swap_fee_percentage}")
    print(f"Pool Hooks Contract: {pool_hooks_contract}")
    print(f"Enable Donation: {enable_donation}")
    print(f"Disable Unbalanced Liquidity: {disable_unbalanced_liquidity}")
    print(f"Salt: {salt}")
    print(f"Gas Limit: {gas_limit}")
    print(f"Gas Price: {base_gas_price}\n")
    
    # Sign and send transaction
    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    
    print(f"🔥 BIG BLOCK Transaction sent: {tx_hash.hex()}")
    
    # Wait for transaction receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"✅ Transaction confirmed in block: {tx_receipt['blockNumber']}")
    
    # Find the PoolCreated event to get the pool address
    pool_address = None
    try:
        pool_created_events = factory.events.PoolCreated().process_receipt(tx_receipt)
        if pool_created_events:
            pool_address = pool_created_events[0]['args']['pool']
    except Exception as e:
        print(f"Error processing events: {str(e)}")
        # Fallback: Try to find event by looking at logs
        for log in tx_receipt['logs']:
            if log['address'].lower() == factory_address.lower():
                try:
                    # This assumes pool address is in the second topic
                    pool_address = w3.to_checksum_address('0x' + log['topics'][1].hex()[-40:])
                    break
                except:
                    continue
    
    if pool_address:
        print(f"🎉 Stable Pool deployed at: {pool_address}")
        return pool_address
    else:
        raise Exception("Pool address not found in transaction logs")

def main():
    # RPC URLs - Hyperliquid
    hyperliquid_rpc_url = "https://rpc.hyperliquid.xyz/evm"
    
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("Private key not provided. Set PRIVATE_KEY environment variable.")
    
    # Stable pool factory address (you'll need to update this)
    factory_address = "0x96484f2aBF5e58b15176dbF1A799627B53F13B6d"  # UPDATE THIS
    
    w3, account = setup_web3(hyperliquid_rpc_url, private_key)
    
    print("🔥 BIG BLOCK STABLE POOL DEPLOYMENT MODE ENABLED 🔥")
    print("This script will ALWAYS use big blocks for deployment\n")
    
    # Set big block flag (you may need to do this manually)
    print("Setting HyperCore big block flag...")
    set_big_block_flag(account.address, private_key)
    
    input("\n⚠️  IMPORTANT: Please ensure your HyperCore account has the big block flag set.")
    input("You can do this via HyperCore interface or by sending the evmUserModify action.")
    input("Press Enter to continue with deployment...")
    
    # Token addresses - These should be stablecoins or similar-value tokens
    token_addresses = [
        "0x02c6a2fA58cC01A18B8D9E00eA48d65E4dF26c70",  # feUSD
        "0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb"  # USDT
    ]
    
    # Amplification parameter for stable pools
    amplification_parameter = 500  # Good default for stablecoin pairs
    
    # Role managers
    pause_manager = '0x082F554A92DA8311A8b6C62ba432b24F33790458'
    swap_fee_manager = '0x082F554A92DA8311A8b6C62ba432b24F33790458'
    pool_creator = '0x0000000000000000000000000000000000000000'

    pool_name = "Stable USDT-feUSD"
    pool_symbol = "S-USDT-feUSD"
    
    # Pool parameters - stable pools typically have lower fees
    swap_fee_percentage = fp(Decimal('0.0005'))  # 0.05% - lower than weighted pools
    
    # Pool hooks contract (zero address for no hooks)
    pool_hooks_contract = '0x0000000000000000000000000000000000000000'
    
    # Liquidity management settings
    enable_donation = False
    disable_unbalanced_liquidity = False
    
    # Salt for deployment
    salt = "0x" + "0" * 64
    
    print("\n🚀 BIG BLOCK STABLE POOL DEPLOYMENT:")
    print(f"Factory address: {factory_address}")
    print(f"Pool name: {pool_name}")
    print(f"Pool symbol: {pool_symbol}")
    print(f"Token addresses: {token_addresses}")
    print(f"Amplification parameter: {amplification_parameter}")
    print(f"Swap fee: {swap_fee_percentage / 1e18 * 100}%")
    print(f"Enable donation: {enable_donation}")
    print(f"Disable unbalanced liquidity: {disable_unbalanced_liquidity}")
    
    print(f"\n📊 About Amplification Parameter:")
    print(f"Current value: {amplification_parameter}")

    
    confirm = input("\n🔥 Proceed with BIG BLOCK stable pool deployment? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Deployment cancelled.")
        return
    
    try:
        # Deploy pool (always using big blocks)
        pool_address = deploy_stable_pool(
            w3, 
            account,
            factory_address, 
            pool_name, 
            pool_symbol,
            token_addresses,
            amplification_parameter,
            pause_manager,
            swap_fee_manager,
            pool_creator,
            swap_fee_percentage,
            pool_hooks_contract,
            enable_donation,
            disable_unbalanced_liquidity,
            salt
        )
        
        print(f"\n🎉 BIG BLOCK Stable Pool deployed successfully at: {pool_address}")
        print(f"💡 Amplification Parameter: {amplification_parameter}")
        print(f"💡 This creates a stable swap optimized for similar-value assets")
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ BIG BLOCK Deployment failed: {error_msg}")
        
        if "exceeds block gas limit" in error_msg:
            print("\n⚠️  Even with big blocks, the transaction is too large!")
            print("Possible solutions:")
            print("1. Verify the big block flag is properly set in HyperCore")
            print("2. Check if your account is converted to a Core user")
            print("3. Try simplifying the transaction")
            print("4. Contact Hyperliquid support")
        else:
            raise e

if __name__ == "__main__":
    main()