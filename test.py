import os
import json
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# States
WALLET = 0

# Replace with your bot token
TOKEN = "7725553169:AAGQEcssaWcz57lHHyWA5FX3GX57eV1o580"

# Constants
COLLECTION_ADDRESS = "EQDmUOKwwa6KU0YFbA_CZTGccRdh5SWIQdBDKg741ecOqzR0"
BASE_URL = "https://toncenter.com/api/v3"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Welcome to the NFT Royalty Checker Bot!\n"
        "Please send me your TON wallet address."
    )
    return WALLET

async def check_nfts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wallet_address = update.message.text.strip()
    
    # Get NFTs for the wallet
    nft_response = requests.get(
        f"{BASE_URL}/nft/items",
        params={
            "owner_address": wallet_address,
            "collection_address": COLLECTION_ADDRESS,
            "limit": 25,
            "offset": 0
        },
        headers={"accept": "application/json"}
    )
    
    nft_data = nft_response.json()
    nft_items = nft_data.get("nft_items", [])
    
    if not nft_items:
        await update.message.reply_text("No NFTs found for this wallet address.")
        return ConversationHandler.END
    
    await update.message.reply_text(f"Found {len(nft_items)} NFT(s). Checking royalties...")
    
    # Check royalties for each NFT
    paid_royalties = 0
    unpaid_royalties = 0
    no_transfer_info = 0
    
    for nft in nft_items:
        nft_address = nft["address"]
        nft_index = nft.get("index", "Unknown")
        
        # Get transfer information
        transfer_response = requests.get(
            f"{BASE_URL}/nft/transfers",
            params={
                "owner_address": wallet_address,
                "item_address": nft_address,
                "collection_address": COLLECTION_ADDRESS,
                "direction": "in",
                "limit": 25,
                "offset": 0,
                "sort": "desc"
            },
            headers={"accept": "application/json"}
        )
        
        transfer_data = transfer_response.json()
        transfers = transfer_data.get("nft_transfers", [])
        
        if transfers:
            latest_transfer = transfers[0]
            forward_amount = latest_transfer.get("forward_amount")
            
            if forward_amount == "1":
                await update.message.reply_text(
                    f"NFT #{nft_index}: Royalty not paid"
                )
                unpaid_royalties += 1
            else:
                await update.message.reply_text(
                    f"NFT #{nft_index}: Royalty paid"
                )
                paid_royalties += 1
        else:
            await update.message.reply_text(
                f"NFT #{nft_index}: No transfer information found"
            )
            no_transfer_info += 1
    
    # Send summary report
    summary = (
        "📊 Royalty Check Summary:\n"
        f"✅ NFTs with paid royalties: {paid_royalties}\n"
        f"❌ NFTs without royalties: {unpaid_royalties}\n"
        f"ℹ️ NFTs with no transfer info: {no_transfer_info}\n"
        f"📝 Total NFTs checked: {len(nft_items)}"
    )
    
    await update.message.reply_text(summary)
    await update.message.reply_text("Royalty check completed!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

def main():
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_nfts)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()