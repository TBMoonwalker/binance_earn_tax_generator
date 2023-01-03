from inspect import trace
from binance.spot import Spot
from regex import R
from datetime import time, date, datetime, timedelta

import configparser
import yfinance as yf
import pandas as pd
import time as clock
import numpy as np

######################################################
#                       Config                       #
######################################################
config = configparser.ConfigParser()
config.read("config.ini")

######################################################
#                      Variables                     #
######################################################
# Binance Client
api_key = config["api"]["key"]
api_secret = config["api"]["secret"]
client = Spot(key=api_key, secret=api_secret)

# CSV data
rewarddate = []
rate_list = []
symbol_list = []
symbol_price_list = []
product_list = []
reward_list = []
reward_price_list = []
tax_list = []

# Date settings
start_date = config["general"]["startdate"]
tr_starts = pd.date_range(start_date, periods=12, freq="MS")
tr_ends = pd.date_range(start_date, periods=12, freq="M")

# Symbol
symbols = list(map(str, config["general"]["token"].split(",")))
products = list(map(str, config["general"]["products"].split(",")))

## Methods
def __token_interest(type: str, symbol: str, start: int, end: int) -> object:

    savings = client.staking_history(
        product="STAKING",
        txnType="INTEREST",
        startTime=start,
        endTime=end,
        size=100,
        asset=symbol,
    )

    if type == "flexible":
        savings = client.savings_interest_history(
            lendingType="DAILY",
            startTime=start,
            endTime=end,
            size=100,
            asset=symbol,
        )

    return savings


def __usd_to_currency(date: datetime, currency: str) -> float:

    price = 0

    end = date + timedelta(days=1)
    start = end - timedelta(days=10)
    prices = yf.Ticker("USD" + currency + "=X").history(
        start=start, end=end, rounding=2
    )
    for i in range(7):
        if date - timedelta(days=i) in prices["Close"].keys():

            price = float(prices["Close"][date - timedelta(days=i)])

    return price


def __symbol_price(symbol: str, timestamp: int) -> float:
    if symbol == "BUSD":
        symbol = symbol + "USDT"
    else:
        symbol = symbol + "BUSD"

    price = client.klines(
        symbol,
        startTime=timestamp,
        interval="1m",
        limit=1,
    )

    return float(price[0][2])


## Logic
for start, end in zip(tr_starts, tr_ends):

    if end < datetime.now():

        end = end + timedelta(hours=24)
        startTimestamp = int(clock.mktime(start.timetuple()) * 1000)
        endTimestamp = int(clock.mktime(end.timetuple()) * 1000)

        for symbol in symbols:

            symbol = symbol.strip()

            for product in products:

                product = product.strip()

                savings = __token_interest(
                    product, symbol, startTimestamp, endTimestamp
                )

                if savings:

                    for interest in savings:

                        interest_amount = 0

                        if product == "locked":
                            interest_amount = interest["amount"]
                        else:
                            interest_amount = interest["interest"]

                        timestamp = datetime.fromtimestamp(int(interest["time"]) / 1000)
                        date = datetime.combine(timestamp, time.min)

                        # No need for currency conversion on USD
                        currency = config["general"]["currency"]
                        if not currency == "USD":
                            rate = __usd_to_currency(date, currency)
                        else:
                            rate = 1

                        symbol_price = __symbol_price(symbol, int(interest["time"]))
                        reward = float(interest_amount)
                        reward_price = (symbol_price * reward) * rate
                        tax = reward_price * (
                            float(config["general"]["taxpercent"]) / 100
                        )

                        rewarddate.append(date)
                        rate_list.append(rate)
                        symbol_list.append(symbol)
                        symbol_price_list.append(symbol_price)
                        product_list.append(product)
                        reward_list.append(reward)
                        reward_price_list.append(reward_price)
                        tax_list.append(tax)

if rewarddate:

    data = pd.DataFrame(
        {
            "Date": rewarddate,
            "Symbol": symbol_list,
            "Product": product_list,
            "Symbol price": symbol_price_list,
            "Reward": reward_list,
            "Exchange rate": rate_list,
            "Reward price": reward_price_list,
            "Tax": tax_list,
        }
    )

    tax_sum = data["Tax"].sum()
    print(tax_sum)

    sum = pd.DataFrame(
        {
            "Date": date.now(),
            "Symbol": np.nan,
            "Product": "Overall tax",
            "Symbol price": np.nan,
            "Reward": np.nan,
            "Exchange rate": np.nan,
            "Reward price": np.nan,
            "Tax": tax_sum,
        },
        index=[0],
    )

    df = pd.concat([data, sum])
    print(df)

    df.sort_values(by="Date", inplace=True)
    df.to_csv("tax.csv", index=False, float_format="%.15f")
else:
    print("No transactions found for " + symbols)
