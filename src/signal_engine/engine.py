import pandas as pd
import datetime as dt
from src.analytics.indicators import (
    get_support_resistance_levels,
    calculate_vwap,
    calculate_volume_sma,
    find_swing_high_low,
    calculate_average_body_size,
    calculate_correlation,
)
from src.pattern_engine.patterns import *
from src.machine_learning.model import get_prediction, prepare_data
from src.machine_learning.correlation_model import get_correlation_prediction, prepare_correlation_data
from src.db.database import Signal
from src.analytics.indicators import calculate_fibonacci_retracement, get_dynamic_levels
import datetime as dt

def calculate_dynamic_tp_sl(entry_price: float, signal_type: str, support_levels: dict, resistance_levels: dict) -> tuple:
    """
    Calculates dynamic take profit and stop loss levels.
    """
    if signal_type == 'CE':
        # For a long trade, SL is the nearest support level
        sl = max([level for level in support_levels.values() if level < entry_price])
        risk = entry_price - sl
        tp1 = entry_price + risk
        tp2 = entry_price + (2 * risk)
        tp3 = entry_price + (3 * risk)
    else: # PE
        # For a short trade, SL is the nearest resistance level
        sl = min([level for level in resistance_levels.values() if level > entry_price])
        risk = sl - entry_price
        tp1 = entry_price - risk
        tp2 = entry_price - (2 * risk)
        tp3 = entry_price - (3 * risk)

    return [tp1, tp2, tp3], sl, risk / (tp1 - entry_price) if tp1 != entry_price else 1


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
    nifty_5m['avg_body_size'] = calculate_average_body_size(nifty_5m)
    correlation = calculate_correlation(nifty_5m, banknifty_5m)

    # 2. Machine Learning
    X, _ = prepare_data(nifty_1d)
    ml_bias_int = get_prediction(X) # 1 for CE, 0 for PE
    ml_bias = "CE" if ml_bias_int == 1 else "PE"

    X_corr, _ = prepare_correlation_data(nifty_5m, banknifty_5m)
    correlation_bias_int = get_correlation_prediction(X_corr)
    correlation_bias = "CE" if correlation_bias_int == 1 else "PE"


    # 3. Signal Generation Logic
    signal = manual_level_strategy(nifty_5m, support_levels, resistance_levels)
    if not signal:
        signal = vwap_strategy(nifty_5m)
    if not signal:
        signal = correlation_strategy(nifty_5m, banknifty_5m, correlation, correlation_bias)
    if not signal:
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
        "correlation": correlation,
        "correlation_bias": correlation_bias,
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
        tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle['close'], signal_type, support_levels, resistance_levels)
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type=signal_type,
            entry_price=last_candle['close'],
            take_profit_levels=','.join(map(str, tp_levels)),
            stop_loss=sl,
            risk_reward_ratio=rr_ratio,
        )

    return None

def correlation_strategy(nifty_df: pd.DataFrame, banknifty_df: pd.DataFrame, correlation: float, correlation_bias: str) -> Signal:
    """
    Generates signals based on Nifty-BankNifty correlation.
    """
    if correlation > 0.8 and correlation_bias == 'CE':
        # If BankNifty is showing bullish momentum, and the correlation is high,
        # and our model predicts a Nifty up-move, then we can take a CE trade.
        last_candle_nifty = nifty_df.iloc[-1]
        last_candle_banknifty = banknifty_df.iloc[-1]
        if last_candle_banknifty['close'] > last_candle_banknifty['open']:
            tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle_nifty['close'], 'CE', nifty_df, nifty_df)
            return Signal(
                timestamp=dt.datetime.now(),
                signal_type='CE',
                entry_price=last_candle_nifty['close'],
                take_profit_levels=','.join(map(str, tp_levels)),
                stop_loss=sl,
                risk_reward_ratio=rr_ratio,
            )

    if correlation > 0.8 and correlation_bias == 'PE':
        # If BankNifty is showing bearish momentum, and the correlation is high,
        # and our model predicts a Nifty down-move, then we can take a PE trade.
        last_candle_nifty = nifty_df.iloc[-1]
        last_candle_banknifty = banknifty_df.iloc[-1]
        if last_candle_banknifty['close'] < last_candle_banknifty['open']:
            tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle_nifty['close'], 'PE', nifty_df, nifty_df)
            return Signal(
                timestamp=dt.datetime.now(),
                signal_type='PE',
                entry_price=last_candle_nifty['close'],
                take_profit_levels=','.join(map(str, tp_levels)),
                stop_loss=sl,
                risk_reward_ratio=rr_ratio,
            )

    return None

def manual_level_strategy(df: pd.DataFrame, support_levels: dict, resistance_levels: dict) -> Signal:
    """
    Generates signals based on manual support and resistance levels.
    This strategy has the highest priority.
    """
    if len(df) < 3:
        return None

    last_candle = df.iloc[-1]
    prev_candle = df.iloc[-2]
    signal_type = None

    # Check for breakouts from manual resistance
    for level_name, level_price in resistance_levels.items():
        if "MANUAL" in level_name:
            if prev_candle['close'] < level_price and last_candle['close'] > level_price:
                signal_type = 'CE'
                break
            # Retest of flipped resistance (now support)
            if prev_candle['high'] > level_price and last_candle['low'] < level_price and last_candle['close'] > level_price and is_pin_bar(df):
                 signal_type = 'CE'
                 break

    if signal_type:
        tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle['close'], signal_type, support_levels, resistance_levels)
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type=signal_type,
            entry_price=last_candle['close'],
            take_profit_levels=','.join(map(str, tp_levels)),
            stop_loss=sl,
            risk_reward_ratio=rr_ratio,
        )

    # Check for breakdowns from manual support
    for level_name, level_price in support_levels.items():
        if "MANUAL" in level_name:
            if prev_candle['close'] > level_price and last_candle['close'] < level_price:
                signal_type = 'PE'
                break
            # Retest of flipped support (now resistance)
            if prev_candle['low'] < level_price and last_candle['high'] > level_price and last_candle['close'] < level_price and is_pin_bar(df):
                signal_type = 'PE'
                break

    if signal_type:
        tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle['close'], signal_type, support_levels, resistance_levels)
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type=signal_type,
            entry_price=last_candle['close'],
            take_profit_levels=','.join(map(str, tp_levels)),
            stop_loss=sl,
            risk_reward_ratio=rr_ratio,
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
            tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle['close'], 'CE', fib_levels, fib_levels)
            return Signal(
                timestamp=dt.datetime.now(),
                signal_type='CE',
                entry_price=last_candle['close'],
                take_profit_levels=','.join(map(str, tp_levels)),
                stop_loss=sl,
                risk_reward_ratio=rr_ratio,
            )

    # Bearish rejection
    for level_type, level_price in fib_levels.items():
        if 'R' in level_type and is_pin_bar(df) and last_candle['high'] > level_price and last_candle['close'] < level_price:
            tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle['close'], 'PE', fib_levels, fib_levels)
            return Signal(
                timestamp=dt.datetime.now(),
                signal_type='PE',
                entry_price=last_candle['close'],
                take_profit_levels=','.join(map(str, tp_levels)),
                stop_loss=sl,
                risk_reward_ratio=rr_ratio,
            )

    return None

def vwap_strategy(df: pd.DataFrame) -> Signal:
    """
    Generates signals based on VWAP breakout and retest logic.
    """
    if len(df) < 3:
        return None

    last_candle = df.iloc[-1]
    prev_candle = df.iloc[-2]
    avg_body_size = df['avg_body_size'].iloc[-1]
    vwap = df['vwap'].iloc[-1]
    signal_type = None

    # VWAP Breakout (Long)
    if prev_candle['close'] < vwap and last_candle['close'] > vwap:
        if abs(last_candle['close'] - last_candle['open']) > avg_body_size:
            signal_type = 'CE'

    # VWAP Breakdown (Short)
    if prev_candle['close'] > vwap and last_candle['close'] < vwap:
        if abs(last_candle['close'] - last_candle['open']) > avg_body_size:
            signal_type = 'PE'

    # VWAP Retest (Long)
    if prev_candle['low'] > vwap and last_candle['low'] < vwap and last_candle['close'] > vwap:
        if is_pin_bar(df) or is_engulfing(df) == "bullish":
            signal_type = 'CE'

    # VWAP Retest (Short)
    if prev_candle['high'] < vwap and last_candle['high'] > vwap and last_candle['close'] < vwap:
        if is_pin_bar(df) or is_engulfing(df) == "bearish":
            signal_type = 'PE'


    if signal_type:
        tp_levels, sl, rr_ratio = calculate_dynamic_tp_sl(last_candle['close'], signal_type, {'vwap': vwap}, {'vwap': vwap})
        return Signal(
            timestamp=dt.datetime.now(),
            signal_type=signal_type,
            entry_price=last_candle['close'],
            take_profit_levels=','.join(map(str, tp_levels)),
            stop_loss=sl,
            risk_reward_ratio=rr_ratio,
        )

    return None
