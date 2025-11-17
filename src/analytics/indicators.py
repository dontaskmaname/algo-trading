import pandas as pd
from sqlalchemy.orm import sessionmaker
from src.db.database import OHLC, engine, ManualLevel

def get_ohlc_data(interval: str, days: int, symbol: str) -> pd.DataFrame:
    """
    Fetches OHLC data from the database.

    Args:
        interval (str): The interval of the data (e.g., '1d', '1h').
        days (int): The number of days to fetch data for.
        symbol (str): The symbol to fetch data for.

    Returns:
        pd.DataFrame: A DataFrame containing the OHLC data.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    query = session.query(OHLC).filter(OHLC.interval == interval, OHLC.symbol == symbol).statement
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

def find_swing_high_low(df: pd.DataFrame, lookback: int = 5) -> tuple:
    """
    Finds the most recent swing high and swing low.

    Args:
        df (pd.DataFrame): A DataFrame containing OHLC data.
        lookback (int): The number of bars to look back on either side.

    Returns:
        tuple: A tuple containing the swing high and swing low.
    """
    if len(df) < lookback * 2 + 1:
        return None, None

    swing_high = None
    swing_low = None

    for i in range(len(df) - lookback -1, lookback, -1):
        is_swing_high = True
        is_swing_low = True
        for j in range(1, lookback + 1):
            if df['high'].iloc[i] < df['high'].iloc[i - j] or df['high'].iloc[i] < df['high'].iloc[i + j]:
                is_swing_high = False
            if df['low'].iloc[i] > df['low'].iloc[i - j] or df['low'].iloc[i] > df['low'].iloc[i + j]:
                is_swing_low = False

        if is_swing_high and not swing_high:
            swing_high = df['high'].iloc[i]
        if is_swing_low and not swing_low:
            swing_low = df['low'].iloc[i]

        if swing_high and swing_low:
            break

    return swing_high, swing_low

def calculate_psychological_levels(price: float, step: int = 50) -> dict:
    """
    Calculates psychological round-number levels.
    """
    lower_level = price - (price % step)
    upper_level = lower_level + step
    return {'PSYCH_S': lower_level, 'PSYCH_R': upper_level}

def get_support_resistance_levels(df_daily: pd.DataFrame, current_price: float) -> dict:
    """
    Consolidates all support and resistance levels into a single dictionary.

    Args:
        df_daily (pd.DataFrame): A DataFrame containing daily OHLC data.
        current_price (float): The current market price.

    Returns:
        dict: A dictionary containing all the support and resistance levels.
    """
    if df_daily.empty:
        return {}

    # Fetch manual levels
    session = sessionmaker(bind=engine)()
    manual_levels = session.query(ManualLevel).all()
    session.close()

    manual_supports = [level.price for level in manual_levels if level.level_type == 'support']
    manual_resistances = [level.price for level in manual_levels if level.level_type == 'resistance']

    # Auto-calculated levels
    pdh, pdl = calculate_previous_day_high_low(df_daily)
    pwh, pwl = calculate_previous_week_high_low(df_daily)
    pmh, pml = calculate_previous_month_high_low(df_daily)
    pivots = calculate_camarilla_pivots(df_daily)
    cpr = calculate_cpr(df_daily)
    psych_levels = calculate_psychological_levels(current_price)

    levels = {
        "PDH": pdh, "PDL": pdl,
        "PWH": pwh, "PWL": pwl,
        "PMH": pmh, "PML": pml,
        **pivots,
        **cpr,
        **psych_levels
    }

    # Give priority to manual levels
    if manual_supports:
        levels['MANUAL_S'] = manual_supports
    # Consolidate all levels into a single dictionary
    all_levels = {
        "PDH": pdh, "PDL": pdl,
        "PWH": pwh, "PWL": pwl,
        "PMH": pmh, "PML": pml,
        **pivots,
        **psych_levels
    }

    # Add manual levels to the dictionary
    for i, price in enumerate(manual_supports):
        all_levels[f"MANUAL_S_{i}"] = price
    for i, price in enumerate(manual_resistances):
        all_levels[f"MANUAL_R_{i}"] = price

    return all_levels

def get_dynamic_levels(all_levels: dict, current_price: float) -> tuple:
    """
    Dynamically determines support and resistance levels based on the current price.
    """
    support_levels = {}
    resistance_levels = {}

    for name, price in all_levels.items():
        if price is None:
            continue
        if price < current_price:
            support_levels[f"S_{name}"] = price
        else:
            resistance_levels[f"R_{name}"] = price

    return support_levels, resistance_levels

def calculate_fibonacci_retracement(df: pd.DataFrame) -> dict:
    """
    Calculates Fibonacci retracement levels.
    """
    swing_high, swing_low = find_swing_high_low(df)

    if swing_high is None or swing_low is None:
        return {}

    price_range = swing_high - swing_low

    return {
        'FIB_S_236': swing_high - (price_range * 0.236),
        'FIB_S_382': swing_high - (price_range * 0.382),
        'FIB_S_500': swing_high - (price_range * 0.5),
        'FIB_S_618': swing_high - (price_range * 0.618),
        'FIB_R_236': swing_low + (price_range * 0.236),
        'FIB_R_382': swing_low + (price_range * 0.382),
        'FIB_R_500': swing_low + (price_range * 0.5),
        'FIB_R_618': swing_low + (price_range * 0.618),
    }

def calculate_average_body_size(df: pd.DataFrame, window: int = 5) -> float:
    """
    Calculates the average body size of the last N candles.

    Args:
        df (pd.DataFrame): A DataFrame containing OHLC data.
        window (int): The number of candles to average.

    Returns:
        float: The average body size.
    """
    if len(df) < window:
        return 0.0

    body_sizes = abs(df['close'] - df['open'])
    return body_sizes.tail(window).mean()

def calculate_correlation(df1: pd.DataFrame, df2: pd.DataFrame, window: int = 20) -> float:
    """
    Calculates the rolling correlation between the close prices of two dataframes.

    Args:
        df1 (pd.DataFrame): The first dataframe.
        df2 (pd.DataFrame): The second dataframe.
        window (int): The rolling window for the correlation.

    Returns:
        float: The latest correlation value.
    """
    if df1.empty or df2.empty or len(df1) < window or len(df2) < window:
        return 0.0

    # Ensure the dataframes are aligned by timestamp
    merged_df = pd.merge(df1, df2, on='timestamp', suffixes=('_1', '_2'))
    if len(merged_df) < window:
        return 0.0

    correlation = merged_df['close_1'].rolling(window=window).corr(merged_df['close_2'])
    return correlation.iloc[-1]

def calculate_cpr(df: pd.DataFrame) -> dict:
    """
    Calculates Central Pivot Range (CPR).
    """
    if df.empty:
        return {}

    last_day = df.iloc[-1]
    high = last_day['high']
    low = last_day['low']
    close = last_day['close']

    pivot = (high + low + close) / 3
    bc = (high + low) / 2
    tc = (pivot - bc) + pivot

    return {'CPR_TOP': tc, 'CPR_PIVOT': pivot, 'CPR_BOTTOM': bc}

if __name__ == '__main__':
    # Example usage
    daily_df = get_ohlc_data('1d', 90) # Fetch last 90 days of daily data

    if not daily_df.empty:
        levels = get_support_resistance_levels(daily_df)
        print("Support and Resistance Levels:")
        for key, value in levels.items():
            print(f"  {key}: {value:.2f}")

        daily_df['vwap'] = calculate_vwap(daily_df)
        print(f"\nVWAP:\n{daily_df[['timestamp', 'vwap']].tail()}")

        daily_df['volume_sma'] = calculate_volume_sma(daily_df)
        print(f"\nVolume SMA9:\n{daily_df[['timestamp', 'volume_sma']].tail()}")
    else:
        print("No data found in the database.")
