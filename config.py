import os
from binance.client import Client

from dotenv import load_dotenv
load_dotenv()

API = "6CmIU2uGFcymC9lovyLogMDuOC0XgX5ktW90kki8atGINKdAF8xgQdb6e30jUuYU"
SECRET = "MNkgqJt9sFTUUOj3a5lqceyvjL1wLymiLLzQsoQvBDOCP5WvzE8XjJ5gvt53215K"

# markets = ['LUNA', 'SAND', 'MATIC', 'NEO', 'GALA', 'BETA', 'TRX', 'AAVE']
# markets = ['BETA', 'LUNA', 'SAND', 'MATIC', 'GALA', 'TRX', 'DOGE']
markets = ['BETA', 'LUNA', 'SAND', 'MATIC']
tick_interval = Client.KLINE_INTERVAL_15MINUTE
