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

    if not access_token:
        secret_key = os.getenv('FYERS_SECRET_KEY')
        redirect_uri = os.getenv('FYERS_REDIRECT_URI')
        if not all([secret_key, redirect_uri]):
            print("Error: For first-time authentication, FYERS_SECRET_KEY and FYERS_REDIRECT_URI must be set in the .env file.")
            return

        try:
            access_token = FyersClient.generate_access_token(
                client_id=client_id,
                secret_key=secret_key,
                redirect_uri=redirect_uri,
                grant_type="authorization_code",
                response_type="code"
            )
            print("\n" + "="*50)
            print("IMPORTANT: Authentication successful!")
            print(f"Your new access token is: {access_token}")
            print("Please save this token in your .env file as `FYERS_ACCESS_TOKEN`.")
            print("The application will now exit. Please restart it after updating the .env file.")
            print("="*50 + "\n")
        except Exception as e:
            print(f"Authentication failed: {e}")
        return

    fyers_client = FyersClient(client_id, access_token)
    print("Fyers client initialized and authenticated successfully.")

    # 3. Fetch initial historical data
    print("Fetching initial historical data...")
    range_to = dt.date.today().strftime('%Y-%m-%d')
    range_from = (dt.date.today() - dt.timedelta(days=60)).strftime('%Y-%m-%d')
    symbol = 'NSE:NIFTY50-INDEX'
    initial_data_fetched = False
    for res, interval in [('5', '5m'), ('15', '15m'), ('60', '1h'), ('D', '1d')]:
        print(f"Fetching {interval} data...")
        hist_data = fyers_client.get_historical_data(symbol, res, '1', range_from, range_to, '1')
        if hist_data:
            fyers_client.store_ohlc_data(hist_data, interval)
            initial_data_fetched = True

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
    df_daily = get_ohlc_data('1d', 60)
    if not df_daily.empty and len(df_daily) > 21:
        X, y = prepare_data(df_daily)
        train_model(X, y)
    else:
        print("Not enough data to train the model.")

    # 5. Generate initial data before starting dashboard
    print("Generating initial market data...")
    initial_market_data = generate_signals('5m', 60)
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
        print("Generating signals and market data...")
        market_data = generate_signals('5m', 60)

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

        time.sleep(300) # Wait for 5 minutes before the next update

if __name__ == '__main__':
    main()
