import yfinance as yf
import pandas as pd
import ta  # 載入我們剛安裝的技術分析套件

ticker_symbol = "0050.TW"
print(f"正在分析 {ticker_symbol} 的多重技術指標...\n")

# 1. 抓取資料
stock = yf.Ticker(ticker_symbol)
hist_data = stock.history(period="6mo")

# 2. 計算技術指標
# 計算 20日均線 (月線)
hist_data['SMA_20'] = hist_data['Close'].rolling(window=20).mean()
# 計算 14日 RSI
hist_data['RSI_14'] = ta.momentum.RSIIndicator(hist_data['Close'], window=14).rsi()

# 3. 取得最新一天的數據
latest_close = hist_data['Close'].iloc[-1]
latest_sma20 = hist_data['SMA_20'].iloc[-1]
latest_rsi = hist_data['RSI_14'].iloc[-1]

print("--- 系統自動判定訊號 ---")
print(f"目前收盤價: {latest_close:.2f}")
print(f"目前月線值: {latest_sma20:.2f}")
print(f"目前 RSI值: {latest_rsi:.2f}")
print("-" * 25)

# 4. 建立雙重決策引擎
is_uptrend = latest_close > latest_sma20  # 條件一：多頭趨勢
is_not_overheated = latest_rsi < 70       # 條件二：尚未過熱

if is_uptrend and is_not_overheated:
    print("🌟 【強烈建議關注】")
    print("👉 結論：目前屬於多頭趨勢，且 RSI 未達超買區 (未過熱)，是相對安全的進場時機！")
elif is_uptrend and not is_not_overheated:
    print("⚠️ 【留意追高風險】")
    print("👉 結論：雖然是多頭趨勢，但 RSI 已超過 70 (市場過熱)，建議等股價稍微拉回再進場。")
elif not is_uptrend and latest_rsi < 30:
    print("💡 【尋找反彈契機】")
    print("👉 結論：目前為空頭趨勢，但 RSI 低於 30 (超賣區)，可能隨時醞釀跌深反彈。")
else:
    print("🛑 【建議觀望】")
    print("👉 結論：目前跌破月線且無明顯超賣訊號，建議保留現金，暫不進場。")