import os
import datetime as dt
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy.orm import sessionmaker
import webbrowser

from src.db.database import OHLC, engine, clear_ohlc_data

class FyersClient:
    """
    A client to interact with the Fyers REST API v3.
    """

    def __init__(self, client_id: str, access_token: str):
        """
        Initializes the FyersClient.
        """
        self.client_id = client_id
        self.access_token = access_token

        log_path_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        if not os.path.exists(log_path_dir):
            os.makedirs(log_path_dir)

        self.fyers = fyersModel.FyersModel(client_id=self.client_id, is_async=False, token=self.access_token, log_path=log_path_dir)

    @staticmethod
    def generate_access_token(client_id: str, secret_key: str, redirect_uri: str, grant_type: str, response_type: str) -> str:
        """
        Runs the interactive authentication flow to generate an access token.
        """
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=secret_key,
            redirect_uri=redirect_uri,
            response_type=response_type,
            grant_type=grant_type
        )
        response = session.generate_authcode()
        print("No access token found. Starting authentication flow.")
        print(f"Please open this URL in your browser to log in: {response}")
        webbrowser.open(response)

        auth_code = input("After logging in, you will be redirected to a URL. Paste the `auth_code` from that URL's query parameters here: ")

        session.set_token(auth_code)
        response = session.generate_token()
        access_token = response.get('access_token')

        if not access_token:
            raise Exception(f"Failed to generate access token. Response: {response}")

        print("Access token generated successfully.")
        return access_token

    def get_historical_data(self, symbol: str, resolution: str, date_format: str, range_from: str, range_to: str, cont_flag: str) -> list:
        """
        Fetches historical data for a given symbol.
        """
        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": date_format,
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": cont_flag
        }
        try:
            response = self.fyers.history(data)
            if response and response.get('candles'):
                return response['candles']
            else:
                print(f"No data received from Fyers API for {symbol}. Response: {response}")
                return []
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return []

    def store_ohlc_data(self, data: list, interval: str, symbol: str):
        """
        Stores OHLC data in the database.
        """
        Session = sessionmaker(bind=engine)
        session = Session()

        for row in data:
            ohlc_data = OHLC(
                timestamp=dt.datetime.fromtimestamp(row[0]),
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                volume=row[5],
                interval=interval,
                symbol=symbol
            )
            session.add(ohlc_data)

        session.commit()
        session.close()

if __name__ == '__main__':
    # Example usage
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'auth', '.env'))
    client_id = os.getenv('FYERS_APP_ID')
    access_token = os.getenv('FYERS_ACCESS_TOKEN')

    if not all([client_id, access_token]):
        print("Error: FYERS_APP_ID and FYERS_ACCESS_TOKEN must be set in the .env file.")
    else:
        client = FyersClient(client_id, access_token)
        print("Fyers client for v3 API created successfully.")

        # Clear existing OHLC data before fetching new data
        print("Clearing existing OHLC data...")
        clear_ohlc_data()
        print("OHLC data cleared.")

        # --- Fetch Daily Nifty Data (5 years) ---
        nifty_daily_symbol = "NSE:NIFTY50-INDEX"
        print(f"\n--- Fetching 5 years of daily data for {nifty_daily_symbol} ---")
        today = dt.date.today()
        for i in range(5):
            range_to = today - dt.timedelta(days=i*365)
            range_from = today - dt.timedelta(days=(i+1)*365)

            print(f"Fetching data from {range_from} to {range_to}...")
            historical_data = client.get_historical_data(nifty_daily_symbol, "D", "1", range_from.strftime('%Y-%m-%d'), range_to.strftime('%Y-%m-%d'), "1")

            if historical_data:
                print(f"Storing {len(historical_data)} records...")
                client.store_ohlc_data(historical_data, '1d', "NIFTY_F1")
                print("Data stored successfully.")

            import time
            time.sleep(1)

        # --- Fetch 5-min Nifty Data (60 days) ---
        nifty_5m_symbol = "NSE:NIFTY50-INDEX"
        print(f"\n--- Fetching 60 days of 5-min data for {nifty_5m_symbol} ---")
        range_to_5m = dt.date.today().strftime('%Y-%m-%d')
        range_from_5m = (dt.date.today() - dt.timedelta(days=60)).strftime('%Y-%m-%d')
        print(f"Fetching data from {range_from_5m} to {range_to_5m}...")
        historical_data_5m = client.get_historical_data(nifty_5m_symbol, "5", "1", range_from_5m, range_to_5m, "1")
        if historical_data_5m:
            print(f"Storing {len(historical_data_5m)} records...")
            client.store_ohlc_data(historical_data_5m, '5m', "NIFTY_F1")
            print("Data stored successfully.")

        # --- Fetch 5-min Bank Nifty Data (60 days) ---
        banknifty_5m_symbol = "NSE:NIFTYBANK-INDEX"
        print(f"\n--- Fetching 60 days of 5-min data for {banknifty_5m_symbol} ---")
        print(f"Fetching data from {range_from_5m} to {range_to_5m}...")
        historical_data_bn_5m = client.get_historical_data(banknifty_5m_symbol, "5", "1", range_from_5m, range_to_5m, "1")
        if historical_data_bn_5m:
            print(f"Storing {len(historical_data_bn_5m)} records...")
            client.store_ohlc_data(historical_data_bn_5m, '5m', "BANKNIFTY_F1")
            print("Data stored successfully.")
