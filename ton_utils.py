# --- START OF FILE ton_utils.py ---

import aiohttp
import requests
import base64
import logging
from typing import Tuple, List, Dict, Optional

logger = logging.getLogger(__name__)

# Configuration (Consider moving these to a central config file/object later)
NFT_COLLECTION_ADDRESS = 'EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0'
TON_API_KEY = "6767227019a948426ee2ef5a310f490e43cc1ca23363b932303002e59988f833" # For Toncenter
TONAPI_KEY = "AHZNMH2YZTTI2NIAAAACRWPE4TMJORYEHELN4ADWSJYBYH475H4AN4FYZUNVNZV4JM74HJY" # For TonAPI.io
SHIVA_TOKEN_ADDRESS = "EQAQAYqUr9IDiiMQKvXXHtLhT77WvbhH7VGhvPPJmBVF3O7y"
VERIFICATION_WALLET = "UQA53kg3IzUo2PTuaZxXB3qK7fICyc1u_Yu8d0JDYJRPVWpz" # For wallet verification tx check

def escape_md(text: str) -> str:
    """MarkdownV2 escaper"""
    escape_chars = '_*[]()~`>#+-=|{}.!-'
    return ''.join(['\\' + char if char in escape_chars else char for char in str(text)])

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
            async with session.get(url, headers=headers, timeout=10) as response:
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
    # Use a known address holding the token to fetch price, or directly query the jetton if API supports it
    # Using the VERIFICATION_WALLET might not always work if it doesn't hold SHIVA
    # A better approach might be querying the jetton master directly if TonAPI supports price info there,
    # or using a known holder like the deployer or a large holder address.
    # Let's stick to the previous method for now, assuming VERIFICATION_WALLET works or is irrelevant for price endpoint.
    url = f"https://tonapi.io/v2/jettons/{SHIVA_TOKEN_ADDRESS}/" # Check Jetton Master endpoint
    # Alternative: url = f"https://tonapi.io/v2/accounts/{SOME_KNOWN_SHIVA_HOLDER}/jettons/{SHIVA_TOKEN_ADDRESS}"
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
             # Fetching general jetton info might contain market data
            async with session.get(url + "masters", headers=headers) as response_master: # Example adjustment
                 if response_master.status == 200:
                      master_data = await response_master.json()
                      # Look for price information within the jetton master data if available
                      # This is hypothetical based on potential API structure
                      if "market_data" in master_data:
                          return master_data["market_data"].get("price", {})

            # Fallback to original method if the above doesn't work or isn't implemented by TonAPI
            # Querying a specific account known to hold the token (if needed)
            price_query_url = f"https://tonapi.io/v2/rates?tokens={SHIVA_TOKEN_ADDRESS}¤cies=ton,usd"
            async with session.get(price_query_url, headers=headers, timeout=10) as response:
                  if response.status != 200:
                        logger.error(f"TonAPI price request failed with status {response.status}")
                        return {}
                  data = await response.json()
                  rates = data.get("rates", {})
                  if SHIVA_TOKEN_ADDRESS in rates:
                       return rates[SHIVA_TOKEN_ADDRESS].get("prices", {}) # Extract prices specifically
                  else:
                       logger.warning(f"Price data not found for {SHIVA_TOKEN_ADDRESS} in rates response.")
                       return {}

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

# --- END OF FILE ton_utils.py ---
