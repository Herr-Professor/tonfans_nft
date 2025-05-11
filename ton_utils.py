# --- START OF FILE ton_utils.py ---

import aiohttp
import requests
import base64
import logging
from typing import Tuple, List, Dict, Optional
import re
import time
import random
import string

logger = logging.getLogger(__name__)

# --- Centralized Configuration ---
NFT_COLLECTION_ADDRESS = 'EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0'
TON_API_KEY = "6767227019a948426ee2ef5a310f490e43cc1ca23363b932303002e59988f833" # For Toncenter
TONAPI_KEY = "AHZNMH2YVN2KADAAAAALIZOB4JXFCW32KUI76NZKQBUULC3RRFH3WEOYKA32KPH27VHWLPY" # For TonAPI.io
SHIVA_TOKEN_ADDRESS = "EQAQAYqUr9IDiiMQKvXXHtLhT77WvbhH7VGhvPPJmBVF3O7y"
VERIFICATION_WALLET = "UQA53kg3IzUo2PTuaZxXB3qK7fICyc1u_Yu8d0JDYJRPVWpz" # For wallet verification tx check
GROUP_INVITE_LINK = "https://t.me/+X44w-gPPj3AzYWU0"
NFT_MARKETPLACE_LINK = "https://getgems.io/collection/EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0"
ADMIN_IDS = ["1499577590", "5851290427"]
GROUP_ID = -1002476568928
BASE_URL = "https://toncenter.com/api/v3"
WELCOME_IMAGE_PATH = "boris.jpg"
SHIVA_DEX_LINK = "https://dedust.io/swap/TON/EQAQAYqUr9IDiiMQKvXXHtLhT77WvbhH7VGhvPPJmBVF3O7y"
PING_ADMIN_ID = 1499577590

def escape_md(text: str) -> str:
    """
    Escapes all special characters for Telegram MarkdownV2.
    """
    if text is None:
        return ''
    text = str(text)
    # List of all special characters for MarkdownV2
    escape_chars = r'[_*\[\]()~`>#+\-=|{}.!]'
    return re.sub(escape_chars, lambda match: '\\' + match.group(0), text)

async def check_nft_ownership(wallet_address: str) -> bool:
    """Checks if a wallet holds an NFT from the specified collection."""
    url = f'https://tonapi.io/v2/accounts/{wallet_address}/nfts?collection={NFT_COLLECTION_ADDRESS}&limit=1000&offset=0&indirect_ownership=false'
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                nft_items = data.get('nft_items', [])
                return len(nft_items) > 0
    except Exception as e:
        logger.error(f"Error checking NFT ownership for {wallet_address}: {e}")
        return False

async def check_transaction(address_to_check: str, required_memo: str) -> bool:
    """Checks the latest transaction to a wallet for a specific memo."""
    API_BASE_URL = "https://toncenter.com/api/v2"
    async with aiohttp.ClientSession() as session:
        try:
            params = {
                "address": address_to_check,
                "limit": 5, # Check last 5 txs for safety
                "api_key": TON_API_KEY
            }
            async with session.get(f"{API_BASE_URL}/getTransactions", params=params) as response:
                if response.status != 200:
                    logger.error(f"Toncenter API request failed with status {response.status} for address {address_to_check}")
                    return False

                data = await response.json()
                if not data.get("ok", False):
                    logger.error(f"Toncenter API request failed: {data.get('error', 'Unknown error')} for address {address_to_check}")
                    return False

                transactions = data.get("result", [])
                if not transactions:
                    logger.info(f"No transactions found for {address_to_check}")
                    return False

                for transaction in transactions:
                    in_msg = transaction.get("in_msg", {})
                    message_data = in_msg.get("message", "") # Renamed from 'message' to avoid conflict
                    decoded_message = ""

                    # Check if message data exists and is base64 encoded
                    msg_content = in_msg.get("msg_data", {}).get("text")
                    if msg_content:
                         try:
                            # Decode base64 text
                            decoded_message = base64.b64decode(msg_content).decode('utf-8', errors='ignore')
                         except Exception:
                            decoded_message = msg_content # Fallback if not base64 or cannot be decoded
                    elif isinstance(message_data, str) and message_data: # Fallback check on raw message if text field not present
                        try:
                           decoded_message = base64.b64decode(message_data).decode('utf-8', errors='ignore')
                        except Exception:
                            decoded_message = message_data # Use as is if not base64

                    logger.debug(f"Checking tx for memo. Found: '{decoded_message}', Required: '{required_memo}'")
                    if required_memo in decoded_message:
                        logger.info(f"Verification memo '{required_memo}' found for address {address_to_check}")
                        return True

                logger.info(f"Verification memo '{required_memo}' not found in recent transactions for address {address_to_check}")
                return False

        except Exception as e:
            logger.error(f"Error checking transaction for address {address_to_check}: {str(e)}")
            return False


async def check_token_balance(user_address: str, jetton_master_address: str) -> Tuple[int, float, Dict]:
    """
    Check jetton token balance and price for a given wallet address.
    Returns raw balance (int), formatted balance (float), and price data (dict).
    """
    url = f"https://tonapi.io/v2/accounts/{user_address}/jettons/{jetton_master_address}"
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=25) as response:
                if response.status == 404: # Wallet might not hold this specific jetton
                    logger.info(f"Jetton {jetton_master_address} not found for address {user_address}. Assuming 0 balance.")
                    return 0, 0.0, {}
                if response.status != 200:
                    logger.error(f"TonAPI request failed with status {response.status} for balance check on {user_address}")
                    return 0, 0.0, {}

                data = await response.json()
                balance = data.get("balance", "0")
                price_data = data.get("price", {})

                raw_balance = int(balance)
                # Assuming 9 decimals for SHIVA, adjust if different
                formatted_balance = raw_balance / 1e9
                logger.debug(f"Token balance for {user_address}: Raw={raw_balance}, Formatted={formatted_balance}")
                return raw_balance, formatted_balance, price_data

    except Exception as e:
        logger.error(f"Error checking token balance for {user_address}: {str(e)}", exc_info=True)
        return 0, 0.0, {}


async def get_shiva_price() -> Dict:
    """Get current SHIVA token price data."""
    try:
        url = f"https://tonapi.io/v2/accounts/{VERIFICATION_WALLET}/jettons/{SHIVA_TOKEN_ADDRESS}"
        params = {
            "currencies": "ton,usd",
            "supported_extensions": "custom_payload"
        }
        headers = {
            "Authorization": f"Bearer {TONAPI_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return {}
                data = await response.json()
                logger.info(f"Price API response: {data}")  # Log the response for debugging
                return data.get("price", {})
    except Exception as e:
        logger.error(f"Error getting SHIVA price: {str(e)}")
        return {}


async def get_top_holders(jetton_master_address: str, limit: int = 10) -> List[Dict]:
    """Get top jetton token holders."""
    url = f"https://tonapi.io/v2/jettons/{jetton_master_address}/holders"
    params = {"limit": limit, "offset": 0}
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=15) as response:
                if response.status != 200:
                    logger.error(f"TonAPI request failed with status {response.status} getting holders for {jetton_master_address}")
                    return []
                data = await response.json()
                return data.get("addresses", [])
    except Exception as e:
        logger.error(f"Error getting top holders for {jetton_master_address}: {str(e)}")
        return []

# === NEW FUNCTIONS FOR JETTON BURN ===

# Define the Jetton master address to use for burns
JETTON_MINTER_ADDRESS = SHIVA_TOKEN_ADDRESS  # Use the SHIVA token address

async def get_jetton_wallet_address(owner_address: str, jetton_minter: str = JETTON_MINTER_ADDRESS) -> Optional[str]:
    """
    Get the Jetton wallet address for a specific owner.
    
    Args:
        owner_address: The TON wallet address of the owner
        jetton_minter: The Jetton minter contract address
        
    Returns:
        The Jetton wallet address or None if lookup fails
    """
    try:
        url = f"https://tonapi.io/v2/accounts/{owner_address}/jettons"
        headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Jetton wallet API request failed: {response.status}")
                    return None
                
                data = await response.json()
                balances = data.get("balances", [])
                
                for balance in balances:
                    if balance.get("jetton_address") == jetton_minter:
                        return balance.get("wallet_address")
                
                logger.warning(f"No Jetton wallet found for {owner_address} and minter {jetton_minter}")
                return None
                
    except Exception as e:
        logger.error(f"Error fetching Jetton wallet address: {str(e)}")
        return None

def generate_message_hash(telegram_id: int, amount: int) -> str:
    """
    Generate a unique hash for a burn request, used for verification.
    
    Args:
        telegram_id: The Telegram user ID
        amount: The amount to burn
        
    Returns:
        A unique hash string
    """
    # Generate a random string to make the hash unique
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    return f"burn_{telegram_id}_{amount}_{random_str}"

async def prepare_burn_transaction(
    jetton_wallet: str, 
    amount: int, 
    message_hash: str
) -> Dict:
    """
    Prepare the burn transaction payload.
    
    Args:
        jetton_wallet: The Jetton wallet address
        amount: The amount to burn (in nanoTokens)
        message_hash: A unique message hash for verification
        
    Returns:
        Transaction payload ready for signing
    """
    # This is a simplified payload for the TON Connect SDK
    # In a real implementation, you'd create the correct cell structure for the burn message
    
    burn_payload = {
        "valid_until": int(time.time()) + 300,  # Valid for 5 minutes
        "messages": [
            {
                "address": jetton_wallet,
                "amount": "50000000",  # 0.05 TON for gas
                "payload": {
                    "op": 0x7bdd97de,  # burn opcode
                    "query_id": 0,
                    "amount": str(amount),
                    "response_destination": "",
                    "custom_payload": message_hash
                }
            }
        ]
    }
    
    return burn_payload

async def burn_jetton(
    owner_address: str, 
    amount_to_burn: int, 
    telegram_id: int = None,
    use_wallet_signature: bool = True
) -> str:
    """
    Burn Jetton tokens.
    
    Args:
        owner_address: The TON wallet address of the owner
        amount_to_burn: Amount to burn (in tokens, will be converted to nanoTokens)
        telegram_id: The Telegram user ID for verification
        use_wallet_signature: Whether to use wallet signature (True for non-custodial)
        
    Returns:
        Transaction hash or empty string if failed
    """
    try:
        # Convert to nanoTokens (assuming 9 decimals)
        amount_nano = amount_to_burn * 1_000_000_000
        
        # Get the Jetton wallet address
        jetton_wallet = await get_jetton_wallet_address(owner_address)
        if not jetton_wallet:
            logger.error(f"Failed to find Jetton wallet for {owner_address}")
            return ""
        
        # Generate a unique message hash for verification
        message_hash = generate_message_hash(telegram_id or 0, amount_to_burn)
        
        if use_wallet_signature:
            # For non-custodial approach, we prepare the payload
            # but rely on the web app to get the user signature
            burn_payload = await prepare_burn_transaction(
                jetton_wallet=jetton_wallet,
                amount=amount_nano,
                message_hash=message_hash
            )
            
            # In a real implementation, you would:
            # 1. Store the burn_payload and message_hash in a database
            # 2. Return information to render the signing page in Telegram
            # 3. Wait for callback from the web app with the signed transaction
            # 4. Broadcast the signed transaction to the TON network
            
            # For demo, we just return the message hash as if it were a tx_hash
            return f"pending_{message_hash}"
        else:
            # For custodial approach (NOT RECOMMENDED):
            # Here you would sign with your own keys and broadcast
            # This would require you to hold user funds which is not secure
            logger.warning("Custodial burn not implemented - not recommended!")
            return ""
        
    except Exception as e:
        logger.error(f"Error in burn_jetton: {str(e)}")
        return ""

# --- END OF FILE ton_utils.py ---
