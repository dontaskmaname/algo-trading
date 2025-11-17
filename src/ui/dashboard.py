import time
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from src.db.database import get_session, Signal
import queue

# Use a queue to pass data from the main thread to the dashboard thread
data_queue = queue.Queue()

def get_signals_from_db():
    """
    Fetches the latest signals from the database.
    """
    session = get_session()
    signals = session.query(Signal).order_by(Signal.timestamp.desc()).limit(10).all()
    session.close()
    return signals

def make_layout() -> Layout:
    """Define the layout of the dashboard."""
    layout = Layout(name="root")

    layout.split(
        Layout(name="header", size=3),
        Layout(ratio=1, name="main"),
        Layout(size=10, name="footer"),
    )

    layout["main"].split_row(Layout(name="side"), Layout(name="body", ratio=2))
    layout["side"].split(Layout(name="info", minimum_size=5), Layout(name="levels", ratio=2))
    return layout

def display_dashboard():
    """
    Displays the CLI dashboard.
    """
    console = Console()
    layout = make_layout()

    start_time = time.time()
    data_received = False
    with Live(layout, screen=True, redirect_stderr=False) as live:
        latest_price = "N/A"
        ml_bias = "N/A"
        correlation = "N/A"
        correlation_bias = "N/A"
        levels = {}
        while True:
            # Block until new data is available
            try:
                data = data_queue.get(timeout=30) # Wait for 30 seconds
                latest_price = data.get("latest_price", "N/A")
                ml_bias = data.get("ml_bias", "N/A")
                correlation = data.get("correlation", "N/A")
                correlation_bias = data.get("correlation_bias", "N/A")
                levels = data.get("levels", {})
                data_received = True
            except queue.Empty:
                # If no data is received for a while, show a waiting message
                if not data_received:
                    info_panel = Panel(
                        Text(
                            "Waiting for initial data from the main application...\n"
                            "This could take a moment. If this persists, check the main console.",
                            justify="left"
                        ),
                        title="[bold yellow]Status[/bold yellow]"
                    )
                    layout["info"].update(info_panel)
                    live.update(layout)
                continue

            # Header
            header = Panel(Text(f"NIFTY AI Trading Dashboard | Last Updated: {time.ctime()}", justify="center"))
            layout["header"].update(header)

            # Info Panel
            price_text = f"[bold green]{latest_price:.2f}[/bold green]" if isinstance(latest_price, (int, float)) else "N/A"
            correlation_text = f"{correlation:.2f}" if isinstance(correlation, (int, float)) else "N/A"
            info_panel = Panel(
                Text(
                    f"NIFTY Price: {price_text}\n"
                    f"ML Bias: [bold cyan]{ml_bias}[/bold cyan]\n"
                    f"Correlation: [bold yellow]{correlation_text}[/bold yellow]\n"
                    f"Correlation Bias: [bold magenta]{correlation_bias}[/bold magenta]",
                    justify="left"
                ),
                title="Market Info"
            )
            layout["info"].update(info_panel)

            # Support and Resistance Panel
            levels_table = Table(title="Support & Resistance")
            levels_table.add_column("Level", style="cyan")
            levels_table.add_column("Price", style="magenta")

            # Sort the levels by price for better readability
            sorted_levels = sorted(levels.items(), key=lambda item: item[1] if item[1] is not None else float('inf'), reverse=True)

            for key, value in sorted_levels:
                if value:
                    levels_table.add_row(key, f"{value:.2f}")
            layout["levels"].update(Panel(levels_table, title="Key Levels"))

            # Signals Table
            signals = get_signals_from_db()
            signals_table = Table(title="Trading Signals")
            signals_table.add_column("Timestamp", style="cyan")
            signals_table.add_column("Type", style="magenta")
            signals_table.add_column("Entry", style="green")
            signals_table.add_column("SL", style="red")
            signals_table.add_column("TP1", style="green")
            signals_table.add_column("TP2", style="green")
            signals_table.add_column("TP3", style="green")
            signals_table.add_column("Status", style="blue")
            for signal in signals:
                signals_table.add_row(
                    str(signal.timestamp.strftime("%Y-%m-%d %H:%M:%S")),
                    signal.signal_type,
                    f"{signal.entry_price:.2f}",
                    f"{signal.sl:.2f}",
                    f"{signal.tp1:.2f}",
                    f"{signal.tp2:.2f}",
                    f"{signal.tp3:.2f}",
                    signal.status,
                )
            layout["body"].update(Panel(signals_table, title="Signals"))

            # Footer - for future use
            layout["footer"].update(Panel("Logs will be displayed here.", title="Log"))

if __name__ == "__main__":
    # Example of how to use the queue
    def simulate_data_feed():
        while True:
            data_queue.put({
                "latest_price": 18500.50,
                "ml_bias": "CE",
                "levels": {"PDH": 18600, "PDL": 18400, "R1": 18550, "S1": 18450}
            })
            time.sleep(5)

    import threading
    producer_thread = threading.Thread(target=simulate_data_feed)
    producer_thread.daemon = True
    producer_thread.start()

    display_dashboard()
