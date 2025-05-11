import os
import aiosqlite
import uvicorn
import logging
import json
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from typing import Dict, Optional
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# TON Connect credentials
PROJECT_ID = "YOUR_TON_CONNECT_PROJECT_ID"
PROJECT_NAME = "TONFANS Jetton Burn"
PROJECT_URL = "https://your-domain.com"
RETURN_URL = f"{PROJECT_URL}/ton-callback"

# Create FastAPI app
app = FastAPI(title="TON Connect Service")

# Add CORS middleware to allow Telegram to load the page
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you might want to restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Setup templates
templates = Jinja2Templates(directory="templates")

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database helper
async def get_db():
    db = await aiosqlite.connect('members.db')
    try:
        yield db
    finally:
        await db.close()

# Save wallet connection
async def save_wallet_connection(telegram_id: int, wallet_address: str, db) -> bool:
    try:
        async with db.cursor() as cursor:
            await cursor.execute('''
                INSERT OR REPLACE INTO user_wallets 
                (telegram_id, wallet_addr, connected_at, last_used)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (telegram_id, wallet_address))
            await db.commit()
        return True
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False

# Models
class TonConnectRequest(BaseModel):
    telegram_id: int
    wallet_address: str

class BurnRequest(BaseModel):
    telegram_id: int
    amount: int
    wallet_address: str

# TON Connect page route
@app.get("/ton-connect", response_class=HTMLResponse)
async def ton_connect(request: Request, telegram_id: int):
    """Renders the TON Connect page for wallet connection"""
    # Create ton_connect.json manifest
    manifest = {
        "url": PROJECT_URL,
        "name": PROJECT_NAME,
        "iconUrl": f"{PROJECT_URL}/static/icon.png"
    }
    
    # Pass variables to template
    return templates.TemplateResponse(
        "connect.html", 
        {
            "request": request, 
            "telegram_id": telegram_id,
            "project_id": PROJECT_ID,
            "project_name": PROJECT_NAME,
            "manifest": json.dumps(manifest),
            "return_url": RETURN_URL
        }
    )

# Callback endpoint for TON Connect
@app.post("/ton-callback")
async def ton_callback(
    request: TonConnectRequest, 
    db: aiosqlite.Connection = Depends(get_db)
):
    """Handles the callback after user connects their wallet"""
    success = await save_wallet_connection(
        request.telegram_id, 
        request.wallet_address,
        db
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save wallet connection")
    
    # Here you would also notify the Telegram bot if needed
    return {"status": "success", "message": "Wallet connected successfully"}

# Burn token page route
@app.get("/ton-burn", response_class=HTMLResponse)
async def ton_burn(request: Request, telegram_id: int, amount: int):
    """Renders the burning page for user to confirm transaction"""
    return templates.TemplateResponse(
        "burn.html", 
        {
            "request": request, 
            "telegram_id": telegram_id,
            "amount": amount,
            "project_id": PROJECT_ID,
            "project_name": PROJECT_NAME
        }
    )

# Burn confirmation callback
@app.post("/burn-callback")
async def burn_callback(request: BurnRequest):
    """Handles the callback after user confirms a burn transaction"""
    # In a real implementation, this would interact with the TON blockchain
    # For now, just return a mock transaction hash
    tx_hash = f"mock_tx_{request.telegram_id}_{request.amount}_{hash(request.wallet_address)}"
    
    # Here you would notify the Telegram bot with the transaction result
    return {
        "status": "success", 
        "tx_hash": tx_hash,
        "message": f"Successfully burned {request.amount} tokens"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "alive"}

if __name__ == "__main__":
    uvicorn.run("ton_connect_app:app", host="0.0.0.0", port=8080, reload=True) 