import os
import datetime as dt
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy.orm import sessionmaker
import webbrowser

from src.db.database import OHLC, engine

class FyersClient:
    """
    A client to interact with the Fyers REST API v3.
    """

    def __init__(self, client_id: str, secret_key: str, redirect_uri: str, grant_type: str, response_type: str):
        """
        Initializes the FyersClient.
        """
        self.client_id = client_id
        self.secret_key = secret_key
        self.redirect_uri = redirect_uri
        self.grant_type = grant_type
        self.response_type = response_type
        self.fyers = None

    def _generate_auth_code(self):
        """
        Generates the authentication code.
        """
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type=self.response_type,
            grant_type=self.grant_type
        )
        response = session.generate_authcode()
        webbrowser.open(response)

    def _set_access_token(self, auth_code: str):
        """
        Sets the access token.
        """
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type=self.response_type,
            grant_type=self.grant_type
        )
        session.set_token(auth_code)
        response = session.generate_token()
        self.fyers = fyersModel.FyersModel(client_id=self.client_id, is_async=False, token=response['access_token'], log_path=os.path.join(os.path.dirname(__file__), '..', '..', 'logs'))

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
        response = self.fyers.history(data)
        return response['candles']

    def store_ohlc_data(self, data: list, interval: str):
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
                interval=interval
            )
            session.add(ohlc_data)

        session.commit()
        session.close()

if __name__ == '__main__':
    # Example usage
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'auth', '.env'))
    client_id = os.getenv('FYERS_APP_ID')
    secret_key = os.getenv('FYERS_SECRET_KEY')
    redirect_uri = os.getenv('FYERS_REDIRECT_URI')
    grant_type = "authorization_code"
    response_type = "code"

    if not all([client_id, secret_key, redirect_uri]):
        print("Error: FYERS_APP_ID, FYERS_SECRET_KEY, and FYERS_REDIRECT_URI must be set in the .env file.")
    else:
        client = FyersClient(client_id, secret_key, redirect_uri, grant_type, response_type)
        print("Fyers client for v3 API created. Authentication flow needs to be completed interactively.")
