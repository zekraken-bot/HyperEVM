from web3 import Web3
import json
import os
from eth_account import Account
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

def fp(number, token_contract):
    decimals = token_contract.functions.decimals().call()
    return int(Decimal(number) * Decimal(10**decimals))

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

base_rpc_url = "https://rpc.hyperliquid.xyz/evm"
w3 = Web3(Web3.HTTPProvider(base_rpc_url))

# Pool and router addresses
pool_address = "0xb537c62307D25F1eb70b720F5850B8C638240F1B"
router_address = "0xA8920455934Da4D853faac1f94Fe7bEf72943eF1"
permit2_address = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

private_key = os.getenv("PRIVATE_KEY")
account = Account.from_key(private_key)
wallet_address = account.address

print(f"Using wallet: {wallet_address}")
print(f"Connected to network with chain ID: {w3.eth.chain_id}")

token_a_address = "0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb"
token_b_address = "0xBe6727B535545C67d5cAa73dEa54865B92CF7907"

# Load token ABIs
with open('erc20_abi.json', 'r') as f:
    erc20_abi = json.load(f)

# Initialize token contracts
token_a_contract = w3.eth.contract(address=token_a_address, abi=erc20_abi)
token_b_contract = w3.eth.contract(address=token_b_address, abi=erc20_abi)

# Set the exact amounts you want to deposit for initialization
token_a_amount = fp(Decimal('0.24'), token_a_contract) 
token_b_amount = fp(Decimal('0.0001'), token_b_contract)

print(f"Token A amount to deposit: {token_a_amount}")
print(f"Token B amount to deposit: {token_b_amount}")

# Load the Permit2 ABI
with open('permit2_abi.json', 'r') as f:
    permit2_abi = json.load(f)

# Check current allowances
token_a_allowance = token_a_contract.functions.allowance(wallet_address, permit2_address).call()
token_b_allowance = token_b_contract.functions.allowance(wallet_address, permit2_address).call()

print(f"Current Token A allowance for Permit2: {token_a_allowance}")
print(f"Current Token B allowance for Permit2: {token_b_allowance}")

# Maximum uint256 value for unlimited approval
max_approval = 2**256 - 1


# Get big block gas price
big_block_gas_price = get_big_block_gas_price(w3)

# Approve tokens for Permit2 if needed
current_nonce = w3.eth.get_transaction_count(wallet_address)

if token_a_allowance < token_a_amount:
    print("Approving Token A for Permit2...")
    approve_tx = token_a_contract.functions.approve(
        permit2_address,
        max_approval
    ).build_transaction({
        "from": wallet_address,
        "gas": 100000,
        "gasPrice": big_block_gas_price,
        "nonce": current_nonce
    })
    
    # Sign and send the approval transaction
    signed_tx = w3.eth.account.sign_transaction(approve_tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Token A approval transaction sent: {tx_hash.hex()}")
    
    # Wait for transaction receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Token A approval status: {'Successful' if tx_receipt.status == 1 else 'Failed'}")
    
    # Increment nonce for next transaction
    current_nonce = w3.eth.get_transaction_count(wallet_address)
else:
    print("Token A already has sufficient allowance")

if token_b_allowance < token_b_amount:
    print("Approving Token B for Permit2...")
    approve_tx = token_b_contract.functions.approve(
        permit2_address,
        max_approval
    ).build_transaction({
        "from": wallet_address,
        "gas": 100000,
        "gasPrice": big_block_gas_price,
        "nonce": current_nonce
    })
    
    # Sign and send the approval transaction
    signed_tx = w3.eth.account.sign_transaction(approve_tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Token B approval transaction sent: {tx_hash.hex()}")
    
    # Wait for transaction receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Token B approval status: {'Successful' if tx_receipt.status == 1 else 'Failed'}")
else:
    print("Token B already has sufficient allowance")

# Load the router ABI
with open('router_abi.json', 'r') as f:
    router_abi = json.load(f)

# Initialize the router contract
router_contract = w3.eth.contract(address=router_address, abi=router_abi)
permit2_contract = w3.eth.contract(address=permit2_address, abi=permit2_abi)

# Query current allowances from Permit2 contract
try:
    token_a_allowance = permit2_contract.functions.allowance(wallet_address, token_a_address, router_address).call()
    token_a_nonce = token_a_allowance[2]  # Extract nonce from allowance tuple
    print(f"Token A Permit2 allowance: {token_a_allowance}, Nonce: {token_a_nonce}")
except Exception as e:
    print(f"Error getting Token A Permit2 allowance: {e}")

try:
    token_b_allowance = permit2_contract.functions.allowance(wallet_address, token_b_address, router_address).call()
    token_b_nonce = token_b_allowance[2]  # Extract nonce from allowance tuple
    print(f"Token B Permit2 allowance: {token_b_allowance}, Nonce: {token_b_nonce}")
except Exception as e:
    print(f"Error getting Token B Permit2 allowance: {e}")

# Initialize pool parameters
initialize_params = {
    "pool": pool_address,
    "tokens": [token_a_address, token_b_address],
    "exactAmountsIn": [token_a_amount, token_b_amount],
    "minBptAmountOut": 0,
    "wethIsEth": False,
    "userData": '0x'
}

initialize_calldata = router_contract.functions.initialize(
    initialize_params["pool"],
    initialize_params["tokens"],
    initialize_params["exactAmountsIn"],
    initialize_params["minBptAmountOut"],
    initialize_params["wethIsEth"],
    initialize_params["userData"]
).build_transaction({'gas': 0, 'gasPrice': 0, 'nonce': 0})['data']

permit2_batch = {
    "details": [
        {
            "token": token_a_address,
            "amount": token_a_amount,
            "expiration": 281474976710655,
            "nonce": token_a_nonce
        },
        {
            "token": token_b_address,
            "amount": token_b_amount,
            "expiration": 281474976710655,
            "nonce": token_b_nonce
        }
    ],
    "spender": router_address,
    "sigDeadline": 115792089237316195423570985008687907853269984665640564039457584007913129639935  # Max deadline
}

PERMIT2_DOMAIN = {
    "name": "Permit2",
    "chainId": w3.eth.chain_id,
    "verifyingContract": permit2_address
}

PERMIT2_TYPES = {
    "PermitBatch": [
        {"name": "details", "type": "PermitDetails[]"},
        {"name": "spender", "type": "address"},
        {"name": "sigDeadline", "type": "uint256"}
    ],
    "PermitDetails": [
        {"name": "token", "type": "address"},
        {"name": "amount", "type": "uint160"},
        {"name": "expiration", "type": "uint48"},
        {"name": "nonce", "type": "uint48"}
    ]
}

# Prepare the structured data for signing
permit2_data = {
    "types": PERMIT2_TYPES,
    "domain": PERMIT2_DOMAIN,
    "primaryType": "PermitBatch",
    "message": permit2_batch
}

# Sign the permit2 message
signed_message = w3.eth.account.sign_typed_data(
    domain_data=permit2_data["domain"],
    message_types=permit2_data["types"],
    message_data=permit2_data["message"],
    private_key=private_key
)

permit2_signature = signed_message.signature.hex()

# Prepare the permitBatchAndCall parameters
permitbatchandcall_params = {
    "permitBatch": [],
    "permitSignatures": [],
    "permit2Batch": permit2_batch,
    "permit2Signature": "0x"+permit2_signature,
    "multicallData": [initialize_calldata]
}

# Build and send the transaction with big block settings
current_nonce = w3.eth.get_transaction_count(wallet_address)

# Use higher gas limit for big blocks
gas_limit = 5000000  # Increased for big blocks

transaction = router_contract.functions.permitBatchAndCall(
    permitbatchandcall_params["permitBatch"],
    permitbatchandcall_params["permitSignatures"],
    permitbatchandcall_params["permit2Batch"],
    permitbatchandcall_params["permit2Signature"],
    permitbatchandcall_params["multicallData"]
).build_transaction({
    "from": wallet_address,
    "gas": gas_limit,
    "gasPrice": big_block_gas_price,  # Use big block gas price
    "nonce": current_nonce
})

print(f"Pool: {pool_address}")
print(f"Token A: {token_a_address} - Amount: {token_a_amount}")
print(f"Token B: {token_b_address} - Amount: {token_b_amount}")
print(f"Gas Limit: {gas_limit}")
print(f"Gas Price: {big_block_gas_price}")

confirm = input("\nProceed with BIG BLOCK pool initialization? (y/n): ").strip().lower()
if confirm != 'y':
    print("Transaction cancelled.")
    exit()

print("Sending transaction...")
signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print(f"Transaction sent! Hash: {tx_hash.hex()}")

tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"✅ Transaction status: {'Successful' if tx_receipt.status == 1 else 'Failed'}")
print(f"✅ Transaction confirmed in block: {tx_receipt['blockNumber']}")

if tx_receipt.status == 1:
    print("🎉 Successfully initialized the pool!")
else:
    print("❌ Transaction failed. Check the transaction hash for details.")