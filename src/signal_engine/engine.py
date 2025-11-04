import pandas as pd
import datetime as dt
from src.analytics.indicators import (
    get_ohlc_data,
    calculate_previous_day_high_low,
    calculate_previous_week_high_low,
    calculate_previous_month_high_low,
    calculate_camarilla_pivots,
    calculate_vwap,
    calculate_volume_sma,
)
from src.pattern_engine.patterns import *
from src.machine_learning.model import get_prediction, prepare_data
from src.db.database import Signal

def generate_signals(interval: str, days: int):
    """
    Generates trading signals based on a combination of analytics, patterns, and ML.
    """
    df = get_ohlc_data(interval, days)

    if df.empty or len(df) < 21:
        print("Not enough data to generate signals.")
        return None

    # 1. Analytics
    pdh, pdl = calculate_previous_day_high_low(df)
    pwh, pwl = calculate_previous_week_high_low(df)
    pmh, pml = calculate_previous_month_high_low(df)
    pivots = calculate_camarilla_pivots(df)
    df['vwap'] = calculate_vwap(df)
    df['volume_sma'] = calculate_volume_sma(df)

    # 2. Machine Learning
    X, _ = prepare_data(df)
    ml_bias = get_prediction(X) # 1 for CE, 0 for PE

    # 3. Pattern Recognition
    pin_bar = is_pin_bar(df)
    engulfing = is_engulfing(df)
    false_breakout = is_false_breakout(df)

    # 4. Signal Generation Logic
    last_candle = df.iloc[-1]

    # Buy Signal (CE)
    if (
        ml_bias == 1 and
        last_candle['close'] > df['vwap'].iloc[-1] and
        last_candle['volume'] > df['volume_sma'].iloc[-1] and
        (pin_bar or engulfing == "bullish" or false_breakout == "bearish") and
        (last_candle['close'] > pdh or last_candle['close'] > pwh or last_candle['close'] > pmh) # SR Confluence
    ):
        entry_price = last_candle['close']
        sl = entry_price - 13
        tp1 = entry_price + 13
        tp2 = entry_price + 26
        tp3 = entry_price + 39
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type='CE',
            entry_price=entry_price,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            sl=sl,
        )

    # Sell Signal (PE)
    elif (
        ml_bias == 0 and
        last_candle['close'] < df['vwap'].iloc[-1] and
        last_candle['volume'] > df['volume_sma'].iloc[-1] and
        (pin_bar or engulfing == "bearish" or false_breakout == "bullish") and
        (last_candle['close'] < pdl or last_candle['close'] < pwl or last_candle['close'] < pml) # SR Confluence
    ):
        entry_price = last_candle['close']
        sl = entry_price + 13
        tp1 = entry_price - 13
        tp2 = entry_price - 26
        tp3 = entry_price - 39
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type='PE',
            entry_price=entry_price,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            sl=sl,
        )
    else:
        return None

if __name__ == '__main__':
    signal = generate_signals('5m', 60)
    if signal:
        print(f"Generated Signal: {signal.signal_type} at {signal.entry_price}")
    else:
        print("No signal generated.")
