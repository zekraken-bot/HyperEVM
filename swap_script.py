from web3 import Web3
import json
import argparse
from eth_account import Account
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up command line arguments
parser = argparse.ArgumentParser(description='Swap tokens using Balancer Router')
parser.add_argument('--token_in', required=True, choices=['TOKEN_A', 'TOKEN_B'], help='Token to swap from')
parser.add_argument('--amount', required=True, type=float, help='Amount to swap (in human-readable format)')
parser.add_argument('--min_amount_out', required=True, type=float, help='Minimum amount to receive (in human-readable format)')
parser.add_argument('--deadline', type=int, default=3600, help='Deadline in seconds from now')
parser.add_argument('--use_permit2', action='store_true', help='Use Permit2 for token approvals')
args = parser.parse_args()

base_rpc_url = "https://rpc.hyperliquid.xyz/evm"
web3 = Web3(Web3.HTTPProvider(base_rpc_url))

# Check connection
if not web3.is_connected():
    raise Exception("Failed to connect to Ethereum node")

# Load private key from environment variable
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
if not PRIVATE_KEY:
    raise Exception("Private key not found in environment variables")

# Set up account
account = Account.from_key(PRIVATE_KEY)
print(f"Using account: {account.address}")

# Contract addresses
ROUTER_ADDRESS = "0xA8920455934Da4D853faac1f94Fe7bEf72943eF1"
POOL_ADDRESS = "0xb537c62307D25F1eb70b720F5850B8C638240F1B"
PERMIT2_ADDRESS = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

# Token addresses and decimals
TOKEN_A = "0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb"
TOKEN_B = "0xBe6727B535545C67d5cAa73dEa54865B92CF7907"
TOKEN_A_DECIMALS = 6
TOKEN_B_DECIMALS = 18

# Load ABIs
with open('router_abi.json', 'r') as f:
    ROUTER_ABI = json.load(f)

with open('erc20_abi.json', 'r') as f:
    ERC20_ABI = json.load(f)

with open('permit2_abi.json', 'r') as f:
    PERMIT2_ABI = json.load(f)

# Initialize contracts
router_contract = web3.eth.contract(address=ROUTER_ADDRESS, abi=ROUTER_ABI)
permit2_contract = web3.eth.contract(address=PERMIT2_ADDRESS, abi=PERMIT2_ABI)

# Set token addresses based on input argument
if args.token_in == 'TOKEN_A':
    token_in_address = TOKEN_A
    token_out_address = TOKEN_B
    token_in_decimals = TOKEN_A_DECIMALS
    token_out_decimals = TOKEN_B_DECIMALS
else:
    token_in_address = TOKEN_B
    token_out_address = TOKEN_A
    token_in_decimals = TOKEN_B_DECIMALS
    token_out_decimals = TOKEN_A_DECIMALS

# Initialize token contracts
token_in_contract = web3.eth.contract(address=token_in_address, abi=ERC20_ABI)
token_out_contract = web3.eth.contract(address=token_out_address, abi=ERC20_ABI)

# Convert human-readable amounts to wei values with correct decimals
amount_in = int(args.amount * (10 ** token_in_decimals))
min_amount_out = int(args.min_amount_out * (10 ** token_out_decimals))

# Calculate deadline timestamp
current_timestamp = web3.eth.get_block('latest').timestamp
deadline = current_timestamp + args.deadline

def approve_token_erc20(token_contract, spender_address, amount):
    """Standard ERC20 approve function"""
    # Check current allowance
    current_allowance = token_contract.functions.allowance(
        account.address, 
        spender_address
    ).call()
    
    if current_allowance >= amount:
        print(f"ERC20 allowance already sufficient: {current_allowance}")
        return
    
    # Build approval transaction
    approve_txn = token_contract.functions.approve(
        spender_address,
        amount
    ).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 100000,  # Adjust as needed
        'gasPrice': web3.eth.gas_price
    })
    
    # Sign and send transaction
    signed_txn = web3.eth.account.sign_transaction(approve_txn, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    
    # Wait for transaction receipt
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"ERC20 approval transaction successful. Hash: {tx_hash.hex()}")
    return tx_receipt

def approve_token_permit2(token_contract, spender_address, amount):
    """First approve Permit2 to spend tokens, then use Permit2 to approve router"""
    # Step 1: First check if token is already approved for Permit2
    current_permit2_allowance = token_contract.functions.allowance(
        account.address, 
        PERMIT2_ADDRESS
    ).call()
    
    if current_permit2_allowance < amount:
        print(f"Approving Permit2 contract to spend {args.token_in}...")
        # Approve Permit2 to spend tokens (this requires a transaction)
        approve_txn = token_contract.functions.approve(
            PERMIT2_ADDRESS,
            2**256 - 1  # Max uint256 for infinite approval
        ).build_transaction({
            'from': account.address,
            'nonce': web3.eth.get_transaction_count(account.address),
            'gas': 100000,
            'gasPrice': web3.eth.gas_price
        })
        
        signed_txn = web3.eth.account.sign_transaction(approve_txn, PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Permit2 approval successful. Hash: {tx_hash.hex()}")
    else:
        print(f"Permit2 already approved to spend {args.token_in}")
    
    # Step 2: Use the Permit2 approve function directly
    # This is simpler than using permit signatures and avoids the EIP-712 error
    print(f"Approving router via Permit2...")
    
    # Approve the router to use tokens via Permit2
    # amount (uint160), expiration (uint48)
    expiration = deadline  # Use the same deadline as the swap
    
    permit2_approve_txn = permit2_contract.functions.approve(
        token_in_address,  # token address
        ROUTER_ADDRESS,    # spender address
        amount_in,         # amount (uint160)
        expiration         # expiration (uint48)
    ).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 200000,
        'gasPrice': web3.eth.gas_price
    })
    
    signed_txn = web3.eth.account.sign_transaction(permit2_approve_txn, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    
    print(f"Permit2 approval for router successful. Hash: {tx_hash.hex()}")
    return tx_receipt

def swap_tokens(router_contract, pool_address, token_in, token_out, amount_in, min_amount_out, deadline):
    """Execute the token swap"""
    # Check token balance before swap
    balance_before = token_in_contract.functions.balanceOf(account.address).call()
    if balance_before < amount_in:
        raise Exception(f"Insufficient balance. Have: {balance_before / (10 ** token_in_decimals)}, Need: {amount_in / (10 ** token_in_decimals)}")
    
    print(f"Swapping {amount_in / (10 ** token_in_decimals)} {args.token_in} for at least {min_amount_out / (10 ** token_out_decimals)} tokens")
    
    # Build swap transaction using swapSingleTokenExactIn
    swap_txn = router_contract.functions.swapSingleTokenExactIn(
        pool_address,  # pool address
        token_in,      # token in
        token_out,     # token out
        amount_in,     # exact amount in
        min_amount_out,# minimum amount out
        deadline,      # deadline
        False,         # wethIsEth flag - set to False as we're using WETH directly
        '0x'           # userData - empty bytes as we don't need custom data
    ).build_transaction({
        'from': account.address,
        'nonce': web3.eth.get_transaction_count(account.address),
        'gas': 500000,  # Adjust as needed
        'gasPrice': web3.eth.gas_price
    })
    
    # Sign and send transaction
    signed_txn = web3.eth.account.sign_transaction(swap_txn, PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)
    
    # Wait for transaction receipt
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Swap transaction successful. Hash: {tx_hash.hex()}")
    
    return tx_receipt

# Main execution
def main():
    try:
        # Approve token spending based on method
        print(f"Approving {args.token_in} for spending...")
        if args.use_permit2:
            approve_token_permit2(token_in_contract, ROUTER_ADDRESS, amount_in)
        else:
            approve_token_erc20(token_in_contract, ROUTER_ADDRESS, amount_in)
        
        # Execute swap
        print("Executing swap...")
        swap_tokens(
            router_contract,
            POOL_ADDRESS,
            token_in_address,
            token_out_address,
            amount_in,
            min_amount_out,
            deadline
        )
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()