from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

CheckButton = KeyboardButton(text='Check for tonfans NFT')
Checkkb = ReplyKeyboardMarkup(keyboard=[[CheckButton]], resize_keyboard=True)

ConnectViaPaymentButton = KeyboardButton(text='Connect via Payment(0.1 ton)')
EnterWalletManuallyButton = KeyboardButton(text='Enter Wallet Manually(free)')
WalletConnectionKb = ReplyKeyboardMarkup(keyboard=[[ConnectViaPaymentButton], [EnterWalletManuallyButton]], resize_keyboard=True)