import pandas as pd
import datetime as dt
from src.analytics.indicators import (
    get_ohlc_data,
    get_support_resistance_levels,
    calculate_vwap,
    calculate_volume_sma,
)
from src.pattern_engine.patterns import *
from src.machine_learning.model import get_prediction, prepare_data
from src.db.database import Signal

def generate_signals(interval: str, days: int):
    """
    Generates trading signals and market data based on a combination of analytics, patterns, and ML.
    """
    df_interval = get_ohlc_data(interval, days)
    df_daily = get_ohlc_data('1d', days)

    if df_interval.empty or df_daily.empty or len(df_interval) < 21:
        print("Not enough data to generate signals.")
        return None

    # 1. Analytics
    levels = get_support_resistance_levels(df_daily)
    df_interval['vwap'] = calculate_vwap(df_interval)
    df_interval['volume_sma'] = calculate_volume_sma(df_interval)

    # 2. Machine Learning
    X, _ = prepare_data(df_daily)
    ml_bias_int = get_prediction(X) # 1 for CE, 0 for PE
    ml_bias = "CE" if ml_bias_int == 1 else "PE"

    # 3. Pattern Recognition
    pin_bar = is_pin_bar(df_interval)
    engulfing = is_engulfing(df_interval)
    false_breakout = is_false_breakout(df_interval)

    # 4. Signal Generation Logic
    last_candle = df_interval.iloc[-1]
    latest_price = last_candle['close']
    signal = None

    # Buy Signal (CE)
    if (
        ml_bias == "CE" and
        last_candle['close'] > df_interval['vwap'].iloc[-1] and
        last_candle['volume'] > df_interval['volume_sma'].iloc[-1] and
        (pin_bar or engulfing == "bullish" or false_breakout == "bearish") and
        (last_candle['close'] > levels.get("PDH", float('inf')) or
         last_candle['close'] > levels.get("PWH", float('inf')) or
         last_candle['close'] > levels.get("PMH", float('inf'))) # SR Confluence
    ):
        entry_price = last_candle['close']
        sl = entry_price - 13
        tp1 = entry_price + 13
        tp2 = entry_price + 26
        tp3 = entry_price + 39
        signal = Signal(
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
        ml_bias == "PE" and
        last_candle['close'] < df_interval['vwap'].iloc[-1] and
        last_candle['volume'] > df_interval['volume_sma'].iloc[-1] and
        (pin_bar or engulfing == "bearish" or false_breakout == "bullish") and
        (last_candle['close'] < levels.get("PDL", float('-inf')) or
         last_candle['close'] < levels.get("PWL", float('-inf')) or
         last_candle['close'] < levels.get("PML", float('-inf'))) # SR Confluence
    ):
        entry_price = last_candle['close']
        sl = entry_price + 13
        tp1 = entry_price - 13
        tp2 = entry_price - 26
        tp3 = entry_price - 39
        signal = Signal(
            timestamp=dt.datetime.now(),
            signal_type='PE',
            entry_price=entry_price,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            sl=sl,
        )

    return {
        "signal": signal,
        "latest_price": latest_price,
        "ml_bias": ml_bias,
        "levels": levels
    }

if __name__ == '__main__':
    result = generate_signals('5m', 60)
    if result and result['signal']:
        signal = result['signal']
        print(f"Generated Signal: {signal.signal_type} at {signal.entry_price}")
    else:
        print("No signal generated.")
