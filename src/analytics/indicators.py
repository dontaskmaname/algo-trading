import pandas as pd
from sqlalchemy.orm import sessionmaker
from src.db.database import OHLC, engine

def get_ohlc_data(interval: str, days: int) -> pd.DataFrame:
    """
    Fetches OHLC data from the database.

    Args:
        interval (str): The interval of the data (e.g., '1d', '1h').
        days (int): The number of days to fetch data for.

    Returns:
        pd.DataFrame: A DataFrame containing the OHLC data.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    query = session.query(OHLC).filter(OHLC.interval == interval).statement
    df = pd.read_sql(query, engine)
    session.close()

    # Ensure the timestamp column is in datetime format
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Filter for the last N days
    end_date = df['timestamp'].max()
    start_date = end_date - pd.Timedelta(days=days)
    df = df[df['timestamp'] >= start_date]

    return df

def calculate_previous_day_high_low(df: pd.DataFrame) -> tuple:
    """
    Calculates the previous day's high and low.

    Args:
        df (pd.DataFrame): A DataFrame containing daily OHLC data.

    Returns:
        tuple: A tuple containing the previous day's high and low.
    """
    if len(df) < 2:
        return None, None
    previous_day = df.iloc[-2]
    return previous_day['high'], previous_day['low']

def calculate_previous_week_high_low(df: pd.DataFrame) -> tuple:
    """
    Calculates the previous week's high and low.

    Args:
        df (pd.DataFrame): A DataFrame containing daily OHLC data.

    Returns:
        tuple: A tuple containing the previous week's high and low.
    """
    df['week'] = df['timestamp'].dt.isocalendar().week
    if len(df['week'].unique()) < 2:
        return None, None
    previous_week_num = df['week'].unique()[-2]
    previous_week_df = df[df['week'] == previous_week_num]
    return previous_week_df['high'].max(), previous_week_df['low'].min()

def calculate_previous_month_high_low(df: pd.DataFrame) -> tuple:
    """
    Calculates the previous month's high and low.

    Args:
        df (pd.DataFrame): A DataFrame containing daily OHLC data.

    Returns:
        tuple: A tuple containing the previous month's high and low.
    """
    df['month'] = df['timestamp'].dt.month
    if len(df['month'].unique()) < 2:
        return None, None
    previous_month_num = df['month'].unique()[-2]
    previous_month_df = df[df['month'] == previous_month_num]
    return previous_month_df['high'].max(), previous_month_df['low'].min()

def calculate_camarilla_pivots(df: pd.DataFrame) -> dict:
    """
    Calculates Camarilla pivot points.

    Args:
        df (pd.DataFrame): A DataFrame containing daily OHLC data.

    Returns:
        dict: A dictionary containing the Camarilla pivot points.
    """
    if df.empty:
        return {}

    last_day = df.iloc[-1]
    high = last_day['high']
    low = last_day['low']
    close = last_day['close']

    pivot = (high + low + close) / 3
    range_ = high - low

    pivots = {
        'R4': close + (range_ * 1.1 / 2),
        'R3': close + (range_ * 1.1 / 4),
        'R2': close + (range_ * 1.1 / 6),
        'R1': close + (range_ * 1.1 / 12),
        'S1': close - (range_ * 1.1 / 12),
        'S2': close - (range_ * 1.1 / 6),
        'S3': close - (range_ * 1.1 / 4),
        'S4': close - (range_ * 1.1 / 2),
        'P': pivot
    }

    return pivots

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Calculates the Volume Weighted Average Price (VWAP).

    Args:
        df (pd.DataFrame): A DataFrame containing OHLCV data.

    Returns:
        pd.Series: A Series containing the VWAP values.
    """
    if df.empty:
        return pd.Series()

    vwap = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    return vwap

def calculate_volume_sma(df: pd.DataFrame, window: int = 9) -> pd.Series:
    """
    Calculates the Simple Moving Average (SMA) of the volume.

    Args:
        df (pd.DataFrame): A DataFrame containing volume data.
        window (int): The window for the SMA.

    Returns:
        pd.Series: A Series containing the volume SMA values.
    """
    if df.empty:
        return pd.Series()

    return df['volume'].rolling(window=window).mean()

if __name__ == '__main__':
    # Example usage
    daily_df = get_ohlc_data('1d', 90) # Fetch last 90 days of daily data

    if not daily_df.empty:
        pdh, pdl = calculate_previous_day_high_low(daily_df)
        print(f"Previous Day High: {pdh}, Previous Day Low: {pdl}")

        pwh, pwl = calculate_previous_week_high_low(daily_df)
        print(f"Previous Week High: {pwh}, Previous Week Low: {pwl}")

        pmh, pml = calculate_previous_month_high_low(daily_df)
        print(f"Previous Month High: {pmh}, Previous Month Low: {pml}")

        pivots = calculate_camarilla_pivots(daily_df)
        print(f"Camarilla Pivots: {pivots}")

        daily_df['vwap'] = calculate_vwap(daily_df)
        print(f"VWAP:\n{daily_df[['timestamp', 'vwap']].tail()}")

        daily_df['volume_sma'] = calculate_volume_sma(daily_df)
        print(f"Volume SMA9:\n{daily_df[['timestamp', 'volume_sma']].tail()}")
    else:
        print("No data found in the database.")
