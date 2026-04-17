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

# --- 資料格式定義 ---
class PortfolioItem(BaseModel):
    ticker: str
    shares: float
    cost: float = 0.0

class PortfolioRequest(BaseModel):
    items: list[PortfolioItem]

# --- 1. 新聞情緒分析引擎 ---
def analyze_news_sentiment(ticker):
    """抓取 Google News 並計算情緒分數"""
    query = urllib.parse.quote(f"{ticker} 股票")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    
    positive_words = ['漲', '高', '創紀錄', '優', '升', '買', '成長', '看好', '多', '強', '大單', '飆']
    negative_words = ['跌', '低', '損', '衰退', '降', '賣', '看壞', '空', '弱', '砍單', '逃']

    total_score = 0
    analyzed_articles = []
    
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        for item in items[:10]:
            title = item.title.text
            score = 0
            for word in positive_words:
                if word in title: score += 1
            for word in negative_words:
                if word in title: score -= 1
                    
            total_score += score
            analyzed_articles.append({"title": title, "sentiment_score": score})
            
        avg_score = total_score / len(analyzed_articles) if analyzed_articles else 0
        return round(avg_score, 2), analyzed_articles
    except Exception as e:
        print(f"抓取新聞失敗: {e}")
        return 0, []

# --- 2. 總市值與損益計算器 ---
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
                
        except exceptions.YFRateLimitError:
            details.append({"ticker": item.ticker, "error": "被 Yahoo 阻擋，請稍後再試"})
        except Exception as e:
            details.append({"ticker": item.ticker, "error": str(e)})
            
        time.sleep(1) # 🌟 防阻擋延遲

    profit_loss_ratio = 0
    if (total_value - total_profit_loss) > 0:
        profit_loss_ratio = round((total_profit_loss / (total_value - total_profit_loss) * 100), 2)

    return {
        "total_portfolio_value": round(total_value, 2),
        "total_profit_loss": round(total_profit_loss, 2),
        "profit_loss_ratio": profit_loss_ratio,
        "details": details
    }

# --- 3. 個股綜合診斷 (含基本面大師指標) ---
@app.get("/analyze/{ticker}")
def analyze_stock(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        hist_data = stock.history(period="6mo")
        
        if hist_data.empty:
            return {"error": "找不到該股票資料，請確認代號是否正確"}

        # --- 抓取基本面資訊 ---
        info = stock.info
        roe = info.get('returnOnEquity')
        peg = info.get('pegRatio')
        profit_margin = info.get('profitMargins')

        tags = []
        # 巴菲特邏輯：高股東權益報酬率 (>15%) 與 高淨利率 (>10%)
        if roe is not None and profit_margin is not None:
            if roe > 0.15 and profit_margin > 0.1:
                tags.append("巴菲特最愛 (高ROE/高淨利)")
        
        # 林奇邏輯：本益成長比低於 1 (代表股價相對盈餘成長被低估)
        if peg is not None:
            if 0 < peg < 1:
                tags.append("林奇式成長 (低PEG)")

        # --- 抓取新聞情緒 ---
        news_score, news_details = analyze_news_sentiment(ticker)

        # --- 技術面計算 ---
        hist_data['SMA_20'] = hist_data['Close'].rolling(window=20).mean()
        hist_data['RSI_14'] = ta.momentum.RSIIndicator(hist_data['Close'], window=14).rsi()

        latest_close = float(hist_data['Close'].iloc[-1])
        latest_sma20 = float(hist_data['SMA_20'].iloc[-1])
        latest_rsi = float(hist_data['RSI_14'].iloc[-1])

        is_uptrend = latest_close > latest_sma20
        is_not_overheated = latest_rsi < 70

        # --- 判定綜合訊號 ---
        if is_uptrend and is_not_overheated and news_score >= 0:
            signal = "🌟 強烈建議關注 (技術面多頭，消息偏多)"
        elif is_uptrend and is_not_overheated and news_score < 0:
            signal = "🤔 技術面漂亮，但消息面偏空，建議縮小部位"
        elif is_uptrend and not is_not_overheated:
            signal = "⚠️ 留意追高風險 (多頭但已過熱)"
        elif not is_uptrend and latest_rsi < 30:
            signal = "💡 尋找反彈契機 (空頭但已超賣)"
        else:
            signal = "🛑 建議觀望 (技術面轉弱)"
            
        # 如果大師指標有亮起，給予特殊加權提示
        if tags and "強烈建議" not in signal:
            signal += " (💡 大師基本面指標亮起，具長線潛力)"

        return {
            "stock": ticker,
            "technical_analysis": {
                "price": round(latest_close, 2),
                "sma_20": round(latest_sma20, 2),
                "rsi_14": round(latest_rsi, 2),
                "trend": "多頭" if is_uptrend else "空頭"
            },
            "fundamentals": {
                "roe": f"{round(roe*100, 2)}%" if roe is not None else "N/A",
                "peg": round(peg, 2) if peg is not None else "N/A",
                "tags": tags
            },
            "news_analysis": {
                "average_sentiment_score": news_score,
                "market_sentiment": "樂觀" if news_score > 0 else "悲觀" if news_score < 0 else "中立",
                "recent_headlines": news_details[:5]
            },
            "final_signal": signal
        }
        
    except exceptions.YFRateLimitError:
        return {"error": "請求頻繁被 Yahoo 阻擋，請等待幾分鐘。"}
    except Exception as e:
        return {"error": f"發生未知錯誤: {str(e)}"}