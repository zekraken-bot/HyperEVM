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

# Function to deploy a weighted pool (always using big blocks)
def deploy_weighted_pool(
    w3, 
    account,
    factory_address, 
    pool_name, 
    pool_symbol,
    token_addresses,
    normalized_weights,
    pause_manager,
    swap_fee_manager,
    pool_creator,
    swap_fee_percentage,
    pool_hooks_contract,
    enable_donation,
    disable_unbalanced_liquidity,
    salt
):
    # Load the factory ABI
    with open("weighted_factory_abi.json", "r") as f:
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
    
    # Sort tokens alphabetically by address and sort weights accordingly
    token_weight_pairs = list(zip(token_config, normalized_weights))
    token_weight_pairs = sorted(token_weight_pairs, key=lambda x: x[0]['token'].lower())
    token_config, normalized_weights = zip(*token_weight_pairs)
    token_config = list(token_config)
    normalized_weights = list(normalized_weights)
    
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
            normalized_weights,
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
        normalized_weights,
        roles_config,
        swap_fee_percentage,
        pool_hooks_contract,
        enable_donation,
        disable_unbalanced_liquidity,
        salt
    ).build_transaction(tx_params)

    print("\n🚀 BIG BLOCK DEPLOYMENT PARAMETERS:")
    print(f"Pool Name: {pool_name}")
    print(f"Pool Symbol: {pool_symbol}")
    print(f"Token Config: {token_config}")
    print(f"Normalized Weights: {normalized_weights}")
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
        print(f"🎉 Pool deployed at: {pool_address}")
        return pool_address
    else:
        raise Exception("Pool address not found in transaction logs")

def main():
    # RPC URLs - Hyperliquid
    hyperliquid_rpc_url = "https://rpc.hyperliquid.xyz/evm"
    
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise Exception("Private key not provided. Set PRIVATE_KEY environment variable.")
    
    # Factory address
    factory_address = "0xE3881627B8DeeBCCF9c23B291430a549Fc0bE5F7"
    
    w3, account = setup_web3(hyperliquid_rpc_url, private_key)
    
    print("🔥 BIG BLOCK DEPLOYMENT MODE ENABLED 🔥")
    print("This script will ALWAYS use big blocks for deployment\n")
    
    # Set big block flag (you may need to do this manually)
    print("Setting HyperCore big block flag...")
    set_big_block_flag(account.address, private_key)
    
    input("\n⚠️  IMPORTANT: Please ensure your HyperCore account has the big block flag set.")
    input("You can do this via HyperCore interface or by sending the evmUserModify action.")
    input("Press Enter to continue with deployment...")
    
    # Token addresses
    token_addresses = [
        "0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb",  # USDT
        "0xBe6727B535545C67d5cAa73dEa54865B92CF7907"   # UETH
    ]
    
    # Normalized weights (must sum to 1e18)
    # 50/50 split for USDT/UETH
    normalized_weights = [
        fp(Decimal('0.5')),  # 50% USDT
        fp(Decimal('0.5'))   # 50% UETH
    ]
    
    # Verify weights sum to 1e18
    total_weight = sum(normalized_weights)
    if total_weight != fp(Decimal('1.0')):
        raise Exception(f"Weights must sum to 1e18, got {total_weight}")
    
    # Role managers
    pause_manager = '0x082F554A92DA8311A8b6C62ba432b24F33790458'
    swap_fee_manager = '0x082F554A92DA8311A8b6C62ba432b24F33790458'
    pool_creator = '0x0000000000000000000000000000000000000000'

    pool_name = "Weighted USDT-UETH"
    pool_symbol = "W-USDT-UETH"
    
    # Pool parameters
    swap_fee_percentage = fp(Decimal('0.0025'))  # 0.25%
    
    # Pool hooks contract (zero address for no hooks)
    pool_hooks_contract = '0x0000000000000000000000000000000000000000'
    
    # Liquidity management settings
    enable_donation = False
    disable_unbalanced_liquidity = False
    
    # Salt for deployment
    salt = "0x" + "0" * 64
    
    print("\n🚀 BIG BLOCK WEIGHTED POOL DEPLOYMENT:")
    print(f"Factory address: {factory_address}")
    print(f"Pool name: {pool_name}")
    print(f"Pool symbol: {pool_symbol}")
    print(f"Token addresses: {token_addresses}")
    print(f"Normalized weights: {[w / 1e18 for w in normalized_weights]}")
    print(f"Swap fee: {swap_fee_percentage / 1e18 * 100}%")
    print(f"Enable donation: {enable_donation}")
    print(f"Disable unbalanced liquidity: {disable_unbalanced_liquidity}")
    
    confirm = input("\n🔥 Proceed with BIG BLOCK deployment? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Deployment cancelled.")
        return
    
    try:
        # Deploy pool (always using big blocks)
        pool_address = deploy_weighted_pool(
            w3, 
            account,
            factory_address, 
            pool_name, 
            pool_symbol,
            token_addresses,
            normalized_weights,
            pause_manager,
            swap_fee_manager,
            pool_creator,
            swap_fee_percentage,
            pool_hooks_contract,
            enable_donation,
            disable_unbalanced_liquidity,
            salt
        )
        
        print(f"\n🎉 BIG BLOCK Weighted pool deployed successfully at: {pool_address}")
        
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