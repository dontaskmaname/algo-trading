import time
import threading
from src.data_ingestion.fyers_client import FyersClient
from src.db.database import init_db, get_session, Signal
from src.machine_learning.model import train_model, prepare_data, get_ohlc_data
from src.signal_engine.engine import generate_signals
from src.ui.dashboard import display_dashboard
import os
from dotenv import load_dotenv
import datetime as dt

def main():
    """
    The main function of the application.
    """
    # 1. Initialize the database
    init_db()

    # 2. Initialize the Fyers client and authenticate
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'src', 'auth', '.env'))
    client_id = os.getenv('FYERS_APP_ID')
    secret_key = os.getenv('FYERS_SECRET_KEY')
    redirect_uri = os.getenv('FYERS_REDIRECT_URI')
    grant_type = "authorization_code"
    response_type = "code"

    if not all([client_id, secret_key, redirect_uri]):
        print("Error: FYERS_APP_ID, FYERS_SECRET_KEY, and FYERS_REDIRECT_URI must be set in the .env file.")
        return

    fyers_client = FyersClient(client_id, secret_key, redirect_uri, grant_type, response_type)

    # The authentication flow is interactive and must be completed by the user
    print("Please complete the authentication flow in your browser.")
    fyers_client._generate_auth_code()
    auth_code = input("Enter the auth code: ")
    fyers_client._set_access_token(auth_code)
    print("Authentication successful.")

    # 3. Fetch initial historical data
    print("Fetching initial historical data...")
    range_to = dt.date.today().strftime('%Y-%m-%d')
    range_from = (dt.date.today() - dt.timedelta(days=60)).strftime('%Y-%m-%d')
    for res, interval in [('5', '5m'), ('15', '15m'), ('60', '1h'), ('D', '1d')]:
        hist_data = fyers_client.get_historical_data('NSE:NIFTY50-INDEX', res, '1', range_from, range_to, '1')
        fyers_client.store_ohlc_data(hist_data, interval)
    print("Initial data fetched and stored.")

    # 4. Run the daily retraining pipeline
    print("Running daily retraining pipeline...")
    df = get_ohlc_data('1d', 60)
    if not df.empty and len(df) > 21:
        X, y = prepare_data(df)
        train_model(X, y)
    else:
        print("Not enough data to train the model.")

    # 5. Start the CLI dashboard in a separate thread
    dashboard_thread = threading.Thread(target=display_dashboard)
    dashboard_thread.daemon = True
    dashboard_thread.start()

    # 6. Main application loop
    while True:
        print("Generating signals...")
        signal = generate_signals('5m', 60)
        if signal:
            session = get_session()
            session.add(signal)
            session.commit()
            session.close()
            print(f"Stored signal: {signal.signal_type} at {signal.entry_price}")
        time.sleep(300) # Wait for 5 minutes

if __name__ == '__main__':
    main()
