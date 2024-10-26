import re
from tonsdk.utils import Address

def is_valid_ton_address(address: str) -> bool:
    try:
        Address(address)
        return True
    except:
        return False

def generate_transfer_link(address: str, amount: int = None, text: str = None):
    base_url = "https://app.tonkeeper.com/transfer/"
    link = f"{base_url}{address}"
    if amount:
        link += f"?amount={amount}"
    if text:
        if amount:
            link += f"&text={text}"
        else:
            link += f"?text={text}"
    return link

def generate_payment_link(user_id: int) -> str:
    # Address of the recipient and the amount to send in nanocoins (1 TON = 1,000,000,000 nanocoins)
    recipient_address = "EQDcKiiJn10ERyU2ntoLLSKv8Uj5CtVSMiWU_2IyAZ2U9XLk"
    amount = 100000000  # 0.1 TON in nanocoins
    message_text = f"Payment for wallet connection - User ID: {user_id}"
    
    return generate_transfer_link(recipient_address, amount, message_text)

# You might want to add more utility functions here, such as:
# - Verifying payments
# - Generating QR codes for payment links
# - Handling wallet connection callbacks