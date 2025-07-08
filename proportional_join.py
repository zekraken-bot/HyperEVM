from web3 import Web3
import json
import os
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

base_rpc_url = "https://rpc.hyperliquid.xyz/evm"
w3 = Web3(Web3.HTTPProvider(base_rpc_url))

pool_address = "0xb537c62307D25F1eb70b720F5850B8C638240F1B"
router_address = "0xA8920455934Da4D853faac1f94Fe7bEf72943eF1"
permit2_address = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

private_key = os.getenv("PRIVATE_KEY")
account = Account.from_key(private_key)
wallet_address = account.address
#wallet_address = "0xcF541D8783f3ac9b5A588723F23E928b887db496"

print(f"Using wallet: {wallet_address}")

# Token details for your pool
token_a_address = "0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb"
token_b_address = "0xBe6727B535545C67d5cAa73dEa54865B92CF7907"

# Specify the desired BPT amount you want to receive
# If you want a specific amount of BPT tokens, set this value
# For example, 1 BPT with 18 decimals would be 1 * 10^18
desired_bpt_amount = 50000000000000000  # 1 BPT with 18 decimals

# Load the pool ABI
with open('weighted_pool_abi.json', 'r') as f:
    pool_abi = json.load(f)

# Initialize the pool contract
pool_contract = w3.eth.contract(address=pool_address, abi=pool_abi)

# Load the router ABI
with open('router_abi.json', 'r') as f:
    router_abi = json.load(f)

# Initialize the router contract
router_contract = w3.eth.contract(address=router_address, abi=router_abi)

# First, call queryAddLiquidityProportional to get the token amounts needed
try:
    print(f"Querying for token amounts needed for {desired_bpt_amount} BPT...")
    query_result = router_contract.functions.queryAddLiquidityProportional(
        pool_address,
        desired_bpt_amount,
        "0x0000000000000000000000000000000000000000",
        "0x"
    ).call()
    
    # query_result should contain the token amounts needed
    # The structure depends on the contract implementation, but it might be an array of token amounts
    print(f"Query result: {query_result}")
    
    # Extract token amounts from the query result
    # The exact structure might need adjustment based on the actual return value
    token_amounts = query_result
    token_a_amount = token_amounts[0]
    token_b_amount = token_amounts[1]
    
    print(f"Token A amount needed: {token_a_amount}")
    print(f"Token B amount needed: {token_b_amount}")
except Exception as e:
    print(f"Error querying add liquidity proportional: {e}")
    # Fallback to default values if query fails
    # token_a_amount = 1000000000000000
    # token_b_amount = 1000000  # Default fallback amount
    # print(f"Using fallback amounts - Token A: {token_a_amount}, Token B: {token_b_amount}")

# Load token ABIs
with open('erc20_abi.json', 'r') as f:
    erc20_abi = json.load(f)

# Initialize token contracts
token_a_contract = w3.eth.contract(address=token_a_address, abi=erc20_abi)
token_b_contract = w3.eth.contract(address=token_b_address, abi=erc20_abi)

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

# Approve tokens for Permit2 if needed
if token_a_allowance < token_a_amount:
    print("Approving Token A for Permit2...")
    approve_tx = token_a_contract.functions.approve(
        permit2_address,
        max_approval
    ).build_transaction({
        "from": wallet_address,
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(wallet_address)
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
    current_nonce = w3.eth.get_transaction_count(wallet_address)

if token_b_allowance < token_b_amount:
    print("Approving Token B for Permit2...")
    approve_tx = token_b_contract.functions.approve(
        permit2_address,
        max_approval
    ).build_transaction({
        "from": wallet_address,
        "gas": 100000,
        "gasPrice": w3.eth.gas_price,
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

# Initialize permit2 contract
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

# Parameters for addLiquidityProportional
add_liquidity_proportional_params = {
    "pool": pool_address,
    "maxAmountsIn": [token_a_amount, token_b_amount],
    "bptAmountOut": desired_bpt_amount,  # Use the desired BPT amount
    "wethIsEth": False,
    "userData": '0x'  # Placeholder for any additional data
}

# Build the calldata for addLiquidityProportional
add_liquidity_proportional_calldata = router_contract.functions.addLiquidityProportional(
    add_liquidity_proportional_params["pool"],
    add_liquidity_proportional_params["maxAmountsIn"],
    add_liquidity_proportional_params["bptAmountOut"],
    add_liquidity_proportional_params["wethIsEth"],
    add_liquidity_proportional_params["userData"]
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
    "multicallData": [add_liquidity_proportional_calldata]
}

# Build and send the transaction with big block settings
current_nonce = w3.eth.get_transaction_count(wallet_address)
gas_limit = 500000  # Adjust as needed

transaction = router_contract.functions.permitBatchAndCall(
    permitbatchandcall_params["permitBatch"],
    permitbatchandcall_params["permitSignatures"],
    permitbatchandcall_params["permit2Batch"],
    permitbatchandcall_params["permit2Signature"],
    permitbatchandcall_params["multicallData"]
).build_transaction({
    "from": wallet_address,
    "gas": gas_limit,
    "gasPrice": w3.eth.gas_price,
    "nonce": current_nonce
})

print("Final transaction ready (permitBatchAndCall):")

signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
print(f"Transaction sent! Hash: {tx_hash.hex()}")
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"Transaction status: {'Successful' if tx_receipt.status == 1 else 'Failed'}")