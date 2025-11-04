import pandas as pd
import datetime as dt
from src.db.database import get_session, Signal
from src.analytics.indicators import (
    get_ohlc_data,
    get_support_resistance_levels,
    calculate_vwap,
    calculate_volume_sma,
)
from src.pattern_engine.patterns import *
from src.machine_learning.model import get_prediction, prepare_data

def backtest_generate_signals(df_interval: pd.DataFrame, df_daily: pd.DataFrame):
    """
    Generates trading signals and market data based on a combination of analytics, patterns, and ML.
    This is a modified version of the original generate_signals function for backtesting.
    """
    if df_interval.empty or df_daily.empty or len(df_interval) < 21:
        return None

    # 1. Analytics
    levels = get_support_resistance_levels(df_daily)
    df_interval.loc[:, 'vwap'] = calculate_vwap(df_interval)
    df_interval.loc[:, 'volume_sma'] = calculate_volume_sma(df_interval)

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
            timestamp=last_candle.name,
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
            timestamp=last_candle.name,
            signal_type='PE',
            entry_price=entry_price,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            sl=sl,
        )

    return {
        "signal": signal,
    }

def run_backtest():
    """
    Runs a backtest of the trading strategy over the last 60 days.
    """
    print("Starting backtest...")

    # 1. Load historical data
    df_5m = get_ohlc_data('5m', 60)
    df_1d = get_ohlc_data('1d', 60)
    df_1d.index = pd.to_datetime(df_1d.index)
    if df_5m.empty or df_1d.empty:
        print("No historical data found. Please run the main application first to fetch data.")
        return

    print(f"Loaded {len(df_5m)} 5m data points and {len(df_1d)} daily data points for backtesting.")

    trades = []
    active_trade = None
    for i in range(21, len(df_5m)):
        current_candle = df_5m.iloc[i]

        # Check if an active trade should be closed
        if active_trade:
            if active_trade.signal_type == 'CE':
                if current_candle['high'] >= active_trade.tp1:
                    active_trade.status = 'TP1'
                    trades.append(active_trade)
                    active_trade = None
                elif current_candle['low'] <= active_trade.sl:
                    active_trade.status = 'SL'
                    trades.append(active_trade)
                    active_trade = None
            elif active_trade.signal_type == 'PE':
                if current_candle['low'] <= active_trade.tp1:
                    active_trade.status = 'TP1'
                    trades.append(active_trade)
                    active_trade = None
                elif current_candle['high'] >= active_trade.sl:
                    active_trade.status = 'SL'
                    trades.append(active_trade)
                    active_trade = None

        # If no trade is active, check for a new signal
        if not active_trade:
            df_5m_window = df_5m.iloc[i-21:i]
            current_day = pd.to_datetime(df_5m_window.index[-1]).date()
            df_1d_window = df_1d[df_1d.index.date <= current_day]

            if df_1d_window.empty:
                continue

            result = backtest_generate_signals(df_5m_window, df_1d_window)

            if result and result['signal']:
                active_trade = result['signal']
                active_trade.status = 'ACTIVE'

    print(f"Completed backtest. Total trades simulated: {len(trades)}")

    # 4. Calculate and display results
    total_trades = len(trades)
    wins = 0
    losses = 0
    total_pnl = 0

    for trade in trades:
        if trade.status == 'TP1':
            wins += 1
            if trade.signal_type == 'CE':
                total_pnl += trade.tp1 - trade.entry_price
            else:
                total_pnl += trade.entry_price - trade.tp1
        elif trade.status == 'SL':
            losses += 1
            if trade.signal_type == 'CE':
                total_pnl += trade.sl - trade.entry_price
            else:
                total_pnl += trade.entry_price - trade.sl

    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0

    print("\n--- Backtest Results ---")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total P/L (in points): {total_pnl:.2f}")
    print("------------------------\n")

if __name__ == '__main__':
    run_backtest()
