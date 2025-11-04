import time
from rich.console import Console
from rich.table import Table
from rich.live import Live
from src.signal_engine.engine import generate_signals
from src.db.database import get_session, Signal

def get_signals_from_db():
    """
    Fetches the latest signals from the database.
    """
    session = get_session()
    signals = session.query(Signal).order_by(Signal.timestamp.desc()).limit(10).all()
    session.close()
    return signals

def display_dashboard():
    """
    Displays the CLI dashboard.
    """
    console = Console()
    table = Table(title="NIFTY AI Trading Signals")

    table.add_column("Timestamp", style="cyan")
    table.add_column("Signal Type", style="magenta")
    table.add_column("Entry Price", style="green")
    table.add_column("TP1", style="yellow")
    table.add_column("TP2", style="yellow")
    table.add_column("TP3", style="yellow")
    table.add_column("SL", style="red")
    table.add_column("Status", style="blue")

    with Live(table, refresh_per_second=4, screen=True) as live:
        while True:
            # 1. Generate new signals
            # In a real application, this would be a more sophisticated process
            # For now, we'll call our existing function and store the signal if one is generated
            # Note: The generate_signals function currently prints to the console,
            # we would need to refactor it to return a signal object.
            # For this example, we'll just fetch from the DB.

            # 2. Fetch signals from the database
            signals = get_signals_from_db()

            # 3. Clear the table and add new rows
            table.rows = []
            for signal in signals:
                table.add_row(
                    str(signal.timestamp),
                    signal.signal_type,
                    f"{signal.entry_price:.2f}",
                    f"{signal.tp1:.2f}",
                    f"{signal.tp2:.2f}",
                    f"{signal.tp3:.2f}",
                    f"{signal.sl:.2f}",
                    signal.status,
                )

            # 4. Update the live display
            live.update(table)

            # 5. Wait for 5 minutes
            time.sleep(300)

if __name__ == "__main__":
    display_dashboard()
