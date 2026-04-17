from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import pandas as pd
import ta
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
from yfinance import exceptions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. 定義資料格式 (加入 cost 成本價) ---
class PortfolioItem(BaseModel):
    ticker: str
    shares: float
    cost: float = 0.0  # 新增成本價，預設為 0

class PortfolioRequest(BaseModel):
    items: list[PortfolioItem]

# --- 2. 核心計算邏輯 (加入損益計算) ---
@app.post("/calculate_portfolio")
def calculate_portfolio(portfolio: PortfolioRequest):
    total_value = 0
    total_profit_loss = 0
    details = []
    
    for item in portfolio.items:
        try:
            stock = yf.Ticker(item.ticker)
            hist_data = stock.history(period="1d")
            
            if not hist_data.empty:
                current_price = float(hist_data['Close'].iloc[-1])
                asset_value = current_price * item.shares
                total_value += asset_value
                
                # 計算單一標的損益
                # 只有當成本價大於 0 時才計算損益
                profit_loss = 0
                if item.cost > 0:
                    profit_loss = (current_price - item.cost) * item.shares
                    total_profit_loss += profit_loss
                
                details.append({
                    "ticker": item.ticker,
                    "shares": item.shares,
                    "cost": item.cost,
                    "current_price": round(current_price, 2),
                    "asset_value": round(asset_value, 2),
                    "profit_loss": round(profit_loss, 2)
                })
            else:
                details.append({"ticker": item.ticker, "error": "無報價資料"})
        except Exception as e:
            details.append({"ticker": item.ticker, "error": str(e)})
        
        time.sleep(1) # 防阻擋延遲

    return {
        "total_portfolio_value": round(total_value, 2),
        "total_profit_loss": round(total_profit_loss, 2),
        "profit_loss_ratio": round((total_profit_loss / (total_value - total_profit_loss) * 100), 2) if (total_value - total_profit_loss) > 0 else 0,
        "details": details
    }

# ... (保留原本的 analyze_news_sentiment 與 analyze_stock 函數) ...
# 注意：請確保你的 analyze_stock 函數還在檔案裡