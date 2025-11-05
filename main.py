import time
import threading
from src.data_ingestion.fyers_client import FyersClient
from src.db.database import init_db, get_session
from src.machine_learning.model import train_model, prepare_data, get_ohlc_data
from src.signal_engine.engine import generate_signals
from src.ui.dashboard import display_dashboard, data_queue
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
    dotenv_path = os.path.join(os.path.dirname(__file__), 'src', 'auth', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    client_id = os.getenv('FYERS_APP_ID')
    access_token = os.getenv('FYERS_ACCESS_TOKEN')

    if not client_id:
        print("Error: FYERS_APP_ID must be set in the .env file.")
        return

    fyers_client = None
    if access_token:
        fyers_client = FyersClient(client_id, access_token)
        # Check if the token is valid by making a test call
        if not fyers_client.get_historical_data('NSE:NIFTY50-INDEX', 'D', '1', (dt.date.today() - dt.timedelta(days=1)).strftime('%Y-%m-%d'), dt.date.today().strftime('%Y-%m-%d'), '1'):
            print("Access token seems to be invalid or expired. Re-authenticating...")
            fyers_client = None # Reset client to trigger re-authentication

    if not fyers_client:
        secret_key = os.getenv('FYERS_SECRET_KEY')
        redirect_uri = os.getenv('FYERS_REDIRECT_URI')
        if not all([secret_key, redirect_uri]):
            print("Error: For first-time authentication, FYERS_SECRET_KEY and FYERS_REDIRECT_URI must be set in the .env file.")
            return

        try:
            new_access_token = FyersClient.generate_access_token(
                client_id=client_id,
                secret_key=secret_key,
                redirect_uri=redirect_uri,
                grant_type="authorization_code",
                response_type="code"
            )
            # Save the new token to the .env file
            with open(dotenv_path, "a") as f:
                f.write(f"\nFYERS_ACCESS_TOKEN={new_access_token}")

            fyers_client = FyersClient(client_id, new_access_token)
            print("Authentication successful and new token saved.")

        except Exception as e:
            print(f"Authentication failed: {e}")
            return

    print("Fyers client initialized and authenticated successfully.")

    # 3. Fetch initial historical data
    print("Fetching initial historical data...")
    range_to = dt.date.today().strftime('%Y-%m-%d')
    range_from = (dt.date.today() - dt.timedelta(days=60)).strftime('%Y-%m-%d')
    nifty_symbol = 'NSE:NIFTY50-INDEX'
    banknifty_futures_symbol = 'NSE:BANKNIFTY25NOVFUT'

    initial_data_fetched = False
    for res, interval in [('5', '5m'), ('15', '15m'), ('60', '1h'), ('D', '1d')]:
        print(f"Fetching {interval} data for {nifty_symbol}...")
        hist_data = fyers_client.get_historical_data(nifty_symbol, res, '1', range_from, range_to, '1')
        if hist_data:
            fyers_client.store_ohlc_data(hist_data, interval, nifty_symbol)
            initial_data_fetched = True

        print(f"Fetching {interval} data for {banknifty_futures_symbol}...")
        hist_data_futures = fyers_client.get_historical_data(banknifty_futures_symbol, res, '1', range_from, range_to, '1')
        if hist_data_futures:
            fyers_client.store_ohlc_data(hist_data_futures, interval, banknifty_futures_symbol)

    if not initial_data_fetched:
        print("\n" + "="*50)
        print("CRITICAL: Failed to fetch any initial historical data.")
        print("This could be due to an invalid access token, API issues, or network problems.")
        print("The application cannot proceed without data. Please try again later.")
        print("="*50 + "\n")
        return
    print("Initial data fetched and stored.")

    # 4. Run the daily retraining pipeline
    print("Running daily retraining pipeline...")
    df_daily = get_ohlc_data('1d', 60, nifty_symbol)
    if not df_daily.empty and len(df_daily) > 21:
        X, y = prepare_data(df_daily)
        train_model(X, y)
    else:
        print("Not enough data to train the model.")

    # 5. Generate initial data before starting dashboard
    print("Generating initial market data...")
    nifty_5m = get_ohlc_data('5m', 60, nifty_symbol)
    nifty_1d = get_ohlc_data('1d', 60, nifty_symbol)
    banknifty_5m = get_ohlc_data('5m', 60, banknifty_futures_symbol)
    initial_market_data = generate_signals(nifty_5m, nifty_1d, banknifty_5m)
    if initial_market_data:
        data_queue.put(initial_market_data)
        signal = initial_market_data.get("signal")
        if signal:
            session = get_session()
            session.add(signal)
            session.commit()
            session.close()
            print(f"Stored initial signal: {signal.signal_type} at {signal.entry_price}")

    # 6. Start the CLI dashboard in a separate thread
    dashboard_thread = threading.Thread(target=display_dashboard)
    dashboard_thread.daemon = True
    dashboard_thread.start()

    # 7. Main application loop
    while True:
        print("Fetching latest market data...")
        # Fetch the latest 5-minute candle
        range_to = dt.date.today().strftime('%Y-%m-%d')
        range_from = (dt.date.today() - dt.timedelta(days=1)).strftime('%Y-%m-%d') # Fetch last day for latest candle
        hist_data = fyers_client.get_historical_data(nifty_symbol, '5', '1', range_from, range_to, '1')
        if hist_data:
            fyers_client.store_ohlc_data(hist_data, '5m', nifty_symbol)
            print("Latest Nifty 5m data fetched and stored.")

        hist_data_futures = fyers_client.get_historical_data(banknifty_futures_symbol, '5', '1', range_from, range_to, '1')
        if hist_data_futures:
            fyers_client.store_ohlc_data(hist_data_futures, '5m', banknifty_futures_symbol)
            print("Latest Bank Nifty Futures 5m data fetched and stored.")

        print("Generating signals and market data...")
        nifty_5m = get_ohlc_data('5m', 60, nifty_symbol)
        nifty_1d = get_ohlc_data('1d', 60, nifty_symbol)
        banknifty_5m = get_ohlc_data('5m', 60, banknifty_futures_symbol)
        market_data = generate_signals(nifty_5m, nifty_1d, banknifty_5m)

        if market_data:
            # Always pass the latest market data to the dashboard
            data_queue.put(market_data)

            # Store signal only if a new one was generated
            signal = market_data.get("signal")
            if signal:
                session = get_session()
                session.add(signal)
                session.commit()
                session.close()
                print(f"Stored signal: {signal.signal_type} at {signal.entry_price}")

        print("Waiting for the next 5-minute interval...")
        time.sleep(300) # Wait for 5 minutes before the next update

if __name__ == '__main__':
    main()
