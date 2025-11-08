import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the database path
data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
db_path = os.path.join(data_dir, 'nifty_ai.db')

# Ensure the data directory exists
os.makedirs(data_dir, exist_ok=True)

db_uri = f'sqlite:///{db_path}'

# Create the engine
engine = create_engine(db_uri)

# Create a base class for declarative models
Base = declarative_base()

class OHLC(Base):
    """OHLC data model."""
    __tablename__ = 'ohlc'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    interval = Column(String, nullable=False)
    symbol = Column(String, nullable=False)

class Signal(Base):
    """Trading signals data model."""
    __tablename__ = 'signals'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    signal_type = Column(String, nullable=False)  # 'CE' or 'PE'
    entry_price = Column(Float, nullable=False)
    take_profit_levels = Column(String, nullable=False) # Comma-separated list of TP levels
    stop_loss = Column(Float, nullable=False)
    risk_reward_ratio = Column(Float, nullable=False)
    status = Column(String, default='active')  # 'active', 'closed'

class Performance(Base):
    """Performance data model."""
    __tablename__ = 'performance'

    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, nullable=True)
    pnl = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    exit_timestamp = Column(DateTime, nullable=False)

class ManualLevel(Base):
    """Manual support and resistance levels."""
    __tablename__ = 'manual_levels'

    id = Column(Integer, primary_key=True)
    level_type = Column(String, nullable=False)  # 'support' or 'resistance'
    price = Column(Float, nullable=False)

def init_db():
    """Initializes the database and creates tables."""
    Base.metadata.create_all(engine)

def get_session():
    """Returns a new database session."""
    Session = sessionmaker(bind=engine)
    return Session()

def clear_ohlc_data():
    """Clears all data from the OHLC table."""
    session = get_session()
    session.query(OHLC).delete()
    session.commit()
    session.close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Initialize or re-initialize the database.")
    parser.add_argument('--reinit', action='store_true', help="Delete and re-initialize the database.")
    args = parser.parse_args()

    if args.reinit:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Deleted existing database at {db_path}")
        init_db()
        print(f'Database re-initialized at {db_path}')
    else:
        init_db()
        print(f'Database initialized at {db_path}')
