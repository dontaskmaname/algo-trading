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
from src.signal_engine.engine import pattern_based_strategy, fibonacci_rejection_strategy
from src.analytics.indicators import calculate_fibonacci_retracement, get_dynamic_levels
from src.db.database import Performance

def log_trade(session, trade: Signal, exit_price: float, exit_timestamp: dt.datetime):
    """Logs a completed trade to the performance table."""
    pnl = 0
    if trade.signal_type == 'CE':
        pnl = exit_price - trade.entry_price
    else:
        pnl = trade.entry_price - exit_price

    performance_log = Performance(
        signal_id=int(trade.timestamp.timestamp()),
        pnl=pnl,
        exit_price=exit_price,
        exit_timestamp=exit_timestamp,
    )
    session.add(performance_log)
    session.commit()

def run_backtest(sl_points: int = 15, tp_ratio: float = 1.0):
    """
    Runs a backtest of the trading strategy over the last 60 days.
    """
    print(f"Starting backtest...")

    session = get_session()

    # 1. Load historical data
    nifty_5m = get_ohlc_data('5m', 60, "NIFTY_F1")
    nifty_1d = get_ohlc_data('1d', 365*5, "NIFTY_F1")
    banknifty_5m = get_ohlc_data('5m', 60, "BANKNIFTY_F1")

    if nifty_5m.empty or nifty_1d.empty or banknifty_5m.empty:
        print("No historical data found. Please run the main application first to fetch data.")
        return

    nifty_5m['volume'] = banknifty_5m['volume']
    nifty_1d.index = pd.to_datetime(nifty_1d.index)

    print(f"Loaded {len(nifty_5m)} 5m data points for backtesting.")

    trades = []
    active_trade = None
    for i in range(50, len(nifty_5m)): # Start from 50 to have enough data for EMAs
        current_candle = nifty_5m.iloc[i]

        # Check if an active trade should be closed
        if active_trade:
            exit_price = None
            exit_timestamp = None

            if active_trade.signal_type == 'CE':
                if current_candle['high'] >= active_trade.tp1:
                    active_trade.status = 'TP1'
                    exit_price = active_trade.tp1
                    exit_timestamp = pd.to_datetime(current_candle.name)
                elif current_candle['low'] <= active_trade.sl:
                    active_trade.status = 'SL'
                    exit_price = active_trade.sl
                    exit_timestamp = pd.to_datetime(current_candle.name)

            elif active_trade.signal_type == 'PE':
                if current_candle['low'] <= active_trade.tp1:
                    active_trade.status = 'TP1'
                    exit_price = active_trade.tp1
                    exit_timestamp = pd.to_datetime(current_candle.name)
                elif current_candle['high'] >= active_trade.sl:
                    active_trade.status = 'SL'
                    exit_price = active_trade.sl
                    exit_timestamp = pd.to_datetime(current_candle.name)

            if exit_price is not None:
                log_trade(session, active_trade, exit_price, exit_timestamp)
                trades.append(active_trade)
                active_trade = None

        # If no trade is active, check for a new signal
        if not active_trade:
            df_5m_window = nifty_5m.iloc[i-50:i]
            current_day = pd.to_datetime(df_5m_window.index[-1]).date()
            df_1d_window = nifty_1d[nifty_1d.index.date <= current_day]

            if df_1d_window.empty:
                continue

            # Get ML Bias
            X, _ = prepare_data(df_1d_window)
            ml_bias_int = get_prediction(X)
            ml_bias = "CE" if ml_bias_int == 1 else "PE"

            last_price = df_5m_window.iloc[-1]['close']
            all_levels = get_support_resistance_levels(df_1d_window, last_price)
            support_levels, resistance_levels = get_dynamic_levels(all_levels, last_price)
            fib_levels = calculate_fibonacci_retracement(df_5m_window)

            signal = fibonacci_rejection_strategy(df_5m_window, fib_levels)
            if not signal:
                signal = pattern_based_strategy(df_5m_window, support_levels, resistance_levels)

            if signal and signal.signal_type == ml_bias:
                signal.sl = signal.entry_price - sl_points if signal.signal_type == 'CE' else signal.entry_price + sl_points
                signal.tp1 = signal.entry_price + (sl_points * tp_ratio) if signal.signal_type == 'CE' else signal.entry_price - (sl_points * tp_ratio)
                active_trade = signal
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

    print(f"\n--- Backtest Results (SL: {sl_points}, TP Ratio: {tp_ratio}) ---")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total P/L (in points): {total_pnl:.2f}")
    print("------------------------\n")

    session.commit()
    session.close()
    print("Backtest results saved to the performance table.")

if __name__ == '__main__':
    run_backtest(sl_points=15, tp_ratio=1.0)
