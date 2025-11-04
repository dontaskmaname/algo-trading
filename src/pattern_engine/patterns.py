import pandas as pd

def is_pin_bar(df: pd.DataFrame) -> bool:
    """Detects a pin bar pattern."""
    if df.empty:
        return False
    last_candle = df.iloc[-1]
    body = abs(last_candle['close'] - last_candle['open'])
    wick = last_candle['high'] - last_candle['low']
    return wick > body * 3

def is_engulfing(df: pd.DataFrame) -> str:
    """Detects a bullish or bearish engulfing pattern."""
    if len(df) < 2:
        return "none"
    last_candle = df.iloc[-1]
    prev_candle = df.iloc[-2]
    if last_candle['close'] > prev_candle['open'] and last_candle['open'] < prev_candle['close']:
        return "bullish"
    elif last_candle['open'] > prev_candle['close'] and last_candle['close'] < prev_candle['open']:
        return "bearish"
    return "none"

def is_doji(df: pd.DataFrame, tolerance: float = 0.05) -> bool:
    """Detects a doji pattern."""
    if df.empty:
        return False
    last_candle = df.iloc[-1]
    body = abs(last_candle['close'] - last_candle['open'])
    price_range = last_candle['high'] - last_candle['low']
    return body / price_range < tolerance if price_range > 0 else False

def is_dragonfly_doji(df: pd.DataFrame) -> bool:
    """Detects a dragonfly doji."""
    if df.empty:
        return False
    last_candle = df.iloc[-1]
    return is_doji(df) and (last_candle['open'] > last_candle['low']) and (last_candle['open'] == last_candle['high'])

def is_gravestone_doji(df: pd.DataFrame) -> bool:
    """Detects a gravestone doji."""
    if df.empty:
        return False
    last_candle = df.iloc[-1]
    return is_doji(df) and (last_candle['open'] < last_candle['high']) and (last_candle['open'] == last_candle['low'])

def is_morning_star(df: pd.DataFrame) -> bool:
    """Detects a morning star pattern."""
    if len(df) < 3:
        return False
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (c1['close'] < c1['open'] and  # Bearish
            c2['close'] < c1['close'] and  # Star
            c3['close'] > c3['open'] and   # Bullish
            c3['close'] > c2['close'] and
            c3['close'] > (c1['open'] + c1['close']) / 2)

def is_evening_star(df: pd.DataFrame) -> bool:
    """Detects an evening star pattern."""
    if len(df) < 3:
        return False
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    return (c1['close'] > c1['open'] and  # Bullish
            c2['close'] > c1['close'] and  # Star
            c3['close'] < c3['open'] and   # Bearish
            c3['close'] < c2['close'] and
            c3['close'] < (c1['open'] + c1['close']) / 2)

def is_harami(df: pd.DataFrame) -> str:
    """Detects a bullish or bearish harami pattern."""
    if len(df) < 2:
        return "none"
    c1, c2 = df.iloc[-2], df.iloc[-1]
    if c1['open'] < c1['close'] and c2['open'] > c2['close'] and \
       c2['open'] < c1['close'] and c2['close'] > c1['open']:
        return "bullish"
    elif c1['open'] > c1['close'] and c2['open'] < c2['close'] and \
         c2['open'] > c1['close'] and c2['close'] < c1['open']:
        return "bearish"
    return "none"

def is_tweezers(df: pd.DataFrame) -> str:
    """Detects tweezers top or bottom pattern."""
    if len(df) < 2:
        return "none"
    c1, c2 = df.iloc[-2], df.iloc[-1]
    if abs(c1['high'] - c2['high']) < (c1['high'] * 0.01) and c1['open'] > c1['close'] and c2['open'] < c2['close']:
        return "top"
    elif abs(c1['low'] - c2['low']) < (c1['low'] * 0.01) and c1['open'] < c1['close'] and c2['open'] > c2['close']:
        return "bottom"
    return "none"

def is_inside_bar(df: pd.DataFrame) -> bool:
    """Detects an inside bar pattern."""
    if len(df) < 2:
        return False
    c1, c2 = df.iloc[-2], df.iloc[-1]
    return c2['high'] < c1['high'] and c2['low'] > c1['low']

def is_false_breakout(df: pd.DataFrame) -> str:
    """Detects a false breakout pattern."""
    if len(df) < 3:
        return "none"
    c1, c2, c3 = df.iloc[-3], df.iloc[-2], df.iloc[-1]
    if c2['high'] > c1['high'] and c3['close'] < c1['high']:
        return "bullish" # Failed breakout to the upside (bearish signal)
    elif c2['low'] < c1['low'] and c3['close'] > c1['low']:
        return "bearish" # Failed breakout to the downside (bullish signal)
    return "none"

if __name__ == '__main__':
    # Example Usage with dummy data
    data = {'timestamp': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
            'open': [100, 110, 90], 'high': [120, 120, 100],
            'low': [80, 80, 80], 'close': [110, 90, 95]}
    df = pd.DataFrame(data)

    print(f"Is Pin Bar: {is_pin_bar(df)}")
    print(f"Is Engulfing: {is_engulfing(df)}")
    print(f"Is Doji: {is_doji(df)}")
    print(f"Is Dragonfly Doji: {is_dragonfly_doji(df)}")
    print(f"Is Gravestone Doji: {is_gravestone_doji(df)}")
    print(f"Is Morning Star: {is_morning_star(df)}")
    print(f"Is Evening Star: {is_evening_star(df)}")
    print(f"Is Harami: {is_harami(df)}")
    print(f"Is Tweezers: {is_tweezers(df)}")
    print(f"Is Inside Bar: {is_inside_bar(df)}")
    print(f"Is False Breakout: {is_false_breakout(df)}")
