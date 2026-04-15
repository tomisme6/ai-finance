from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # 新增：用來定義資料格式
import yfinance as yf
import pandas as pd
import ta
import requests
from bs4 import BeautifulSoup
import urllib.parse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- 升級版：Google News 爬蟲與情緒分析引擎 ---
def analyze_news_sentiment(ticker):
    """
    自動去 Google News 抓取該股票的最新 10 則新聞，並計算情緒分數。
    """
    # 1. 組合 Google News RSS 網址 (搜尋 股票代號 + 股票)
    query = urllib.parse.quote(f"{ticker} 股票")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    positive_words = ['漲', '高', '創紀錄', '優', '升', '買', '成長', '看好', '多', '強', '大單', '飆']
    negative_words = ['跌', '低', '損', '衰退', '降', '賣', '看壞', '空', '弱', '砍單', '逃']

    total_score = 0
    analyzed_articles = []
    
    try:
        # 2. 發送請求並解析 XML
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item') # 抓取每一則新聞
        
        # 取最新 10 則新聞來分析
        for item in items[:10]:
            title = item.title.text
            score = 0
            
            for word in positive_words:
                if word in title:
                    score += 1
            for word in negative_words:
                if word in title:
                    score -= 1
                    
            total_score += score
            analyzed_articles.append({
                "title": title,
                "sentiment_score": score
            })
            
        avg_score = total_score / len(analyzed_articles) if analyzed_articles else 0
        return round(avg_score, 2), analyzed_articles
        
    except Exception as e:
        print(f"抓取新聞失敗: {e}")
        return 0, []

# ------------------------------------------------

@app.get("/analyze/{ticker}")
def analyze_stock(ticker: str):
    stock = yf.Ticker(ticker)
    
    hist_data = stock.history(period="6mo")
    if hist_data.empty:
        return {"error": "找不到該股票資料，請確認代號是否正確 (台股記得加 .TW)"}

    # 🛑 這裡要修改！改用我們新寫的 Google News 函數
    news_score, news_details = analyze_news_sentiment(ticker)

    hist_data['SMA_20'] = hist_data['Close'].rolling(window=20).mean()
    hist_data['RSI_14'] = ta.momentum.RSIIndicator(hist_data['Close'], window=14).rsi()

    latest_close = float(hist_data['Close'].iloc[-1])
    latest_sma20 = float(hist_data['SMA_20'].iloc[-1])
    latest_rsi = float(hist_data['RSI_14'].iloc[-1])

    is_uptrend = latest_close > latest_sma20
    is_not_overheated = latest_rsi < 70

    if is_uptrend and is_not_overheated and news_score >= 0:
        signal = "🌟 強烈建議關注 (技術面多頭且未過熱，消息面偏多或中立)"
    elif is_uptrend and is_not_overheated and news_score < 0:
        signal = "🤔 技術面漂亮，但消息面偏空，建議縮小部位試單"
    elif is_uptrend and not is_not_overheated:
        signal = "⚠️ 留意追高風險 (多頭但已過熱)"
    elif not is_uptrend and latest_rsi < 30:
        signal = "💡 尋找反彈契機 (空頭但已超賣)"
    else:
        signal = "🛑 建議觀望 (技術面轉弱，暫不進場)"

    return {
        "stock": ticker,
        "technical_analysis": {
            "price": round(latest_close, 2),
            "sma_20": round(latest_sma20, 2),
            "rsi_14": round(latest_rsi, 2),
            "trend": "多頭" if is_uptrend else "空頭"
        },
        "news_analysis": {
            "average_sentiment_score": news_score,
            "market_sentiment": "樂觀" if news_score > 0 else "悲觀" if news_score < 0 else "中立",
            "recent_headlines": news_details[:5]
        },
        "final_signal": signal
    }
# === 以下是這次新增的「投資組合結算」模組 ===

# 定義前端傳過來的資料格式
class PortfolioItem(BaseModel):
    ticker: str
    shares: float

class PortfolioRequest(BaseModel):
    items: list[PortfolioItem]

@app.post("/calculate_portfolio")
def calculate_portfolio(portfolio: PortfolioRequest):
    total_value = 0
    details = []
    
    for item in portfolio.items:
        try:
            # 抓取最新一天的收盤價
            stock = yf.Ticker(item.ticker)
            hist_data = stock.history(period="1d")
            
            if not hist_data.empty:
                current_price = float(hist_data['Close'].iloc[-1])
                asset_value = current_price * item.shares
                total_value += asset_value
                
                details.append({
                    "ticker": item.ticker,
                    "shares": item.shares,
                    "current_price": round(current_price, 2),
                    "asset_value": round(asset_value, 2)
                })
            else:
                details.append({"ticker": item.ticker, "error": "無報價資料"})
        except Exception as e:
            details.append({"ticker": item.ticker, "error": str(e)})
            
    return {
        "total_portfolio_value": round(total_value, 2),
        "details": details
    }