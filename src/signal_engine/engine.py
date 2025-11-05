import pandas as pd
import datetime as dt
from src.analytics.indicators import (
    get_support_resistance_levels,
    calculate_vwap,
    calculate_volume_sma,
    find_swing_high_low,
)
from src.pattern_engine.patterns import *
from src.machine_learning.model import get_prediction, prepare_data
from src.db.database import Signal
from src.analytics.indicators import calculate_fibonacci_retracement, get_dynamic_levels
import datetime as dt

def generate_signals(nifty_5m: pd.DataFrame, nifty_1d: pd.DataFrame, banknifty_5m: pd.DataFrame):
    """
    Generates trading signals and market data based on a combination of analytics, patterns, and ML.
    """
    if nifty_5m.empty or nifty_1d.empty or banknifty_5m.empty or len(nifty_5m) < 21:
        print("Not enough data to generate signals.")
        return None

    # Merge the volume from banknifty futures into the nifty 5m data
    nifty_5m['volume'] = banknifty_5m['volume']

    # 1. Analytics
    last_price = nifty_5m.iloc[-1]['close']
    all_levels = get_support_resistance_levels(nifty_1d, last_price)
    support_levels, resistance_levels = get_dynamic_levels(all_levels, last_price)
    nifty_5m['vwap'] = calculate_vwap(nifty_5m)
    nifty_5m['volume_sma'] = calculate_volume_sma(nifty_5m)

    # 2. Machine Learning
    X, _ = prepare_data(nifty_1d)
    ml_bias_int = get_prediction(X) # 1 for CE, 0 for PE
    ml_bias = "CE" if ml_bias_int == 1 else "PE"

    # 3. Signal Generation Logic
    fib_levels = calculate_fibonacci_retracement(nifty_5m)
    signal = fibonacci_rejection_strategy(nifty_5m, fib_levels)
    if not signal:
        signal = pattern_based_strategy(nifty_5m, support_levels, resistance_levels)

    # 4. Signal Filtering
    # Apply the ML bias filter
    if signal and signal.signal_type != ml_bias:
        signal = None

    latest_price = nifty_5m.iloc[-1]['close']

    return {
        "signal": signal,
        "latest_price": latest_price,
        "ml_bias": ml_bias,
        "levels": all_levels
    }

def pattern_based_strategy(df: pd.DataFrame, support_levels: dict, resistance_levels: dict) -> Signal:
    """
    Generates signals based on candlestick patterns at key dynamic S/R levels.
    """
    last_candle = df.iloc[-1]
    signal_type = None

    # Bullish patterns
    if is_hammer(df) or is_engulfing(df) == "bullish" or is_morning_star(df) or is_tweezers(df) == "bottom":
        # Check for confluence with a dynamic support level
        for level_type, level_price in support_levels.items():
            if abs(last_candle['low'] - level_price) < (last_candle['low'] * 0.002):
                signal_type = 'CE'
                break

    # Bearish patterns
    if is_shooting_star(df) or is_engulfing(df) == "bearish" or is_evening_star(df) or is_tweezers(df) == "top":
        # Check for confluence with a dynamic resistance level
        for level_type, level_price in resistance_levels.items():
            if abs(last_candle['high'] - level_price) < (last_candle['high'] * 0.002):
                signal_type = 'PE'
                break

    if signal_type:
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type=signal_type,
            entry_price=last_candle['close'],
            tp1=last_candle['close'] + 15 if signal_type == 'CE' else last_candle['close'] - 15,
            tp2=last_candle['close'] + 30 if signal_type == 'CE' else last_candle['close'] - 30,
            tp3=last_candle['close'] + 45 if signal_type == 'CE' else last_candle['close'] - 45,
            sl=last_candle['close'] - 15 if signal_type == 'CE' else last_candle['close'] + 15,
        )

    return None

def fibonacci_rejection_strategy(df: pd.DataFrame, fib_levels: dict) -> Signal:
    """
    Generates signals based on price rejection at Fibonacci levels.
    """
    if not fib_levels:
        return None

    last_candle = df.iloc[-1]

    # Bullish rejection
    for level_type, level_price in fib_levels.items():
        if 'S' in level_type and is_pin_bar(df) and last_candle['low'] < level_price and last_candle['close'] > level_price:
            return Signal(
                timestamp=dt.datetime.now(),
                signal_type='CE',
                entry_price=last_candle['close'],
                tp1=last_candle['close'] + 15,
                tp2=last_candle['close'] + 30,
                tp3=last_candle['close'] + 45,
                sl=last_candle['close'] - 15,
            )

    # Bearish rejection
    for level_type, level_price in fib_levels.items():
        if 'R' in level_type and is_pin_bar(df) and last_candle['high'] > level_price and last_candle['close'] < level_price:
            return Signal(
                timestamp=dt.datetime.now(),
                signal_type='PE',
                entry_price=last_candle['close'],
                tp1=last_candle['close'] - 15,
                tp2=last_candle['close'] - 30,
                tp3=last_candle['close'] - 45,
                sl=last_candle['close'] + 15,
            )

    return None
