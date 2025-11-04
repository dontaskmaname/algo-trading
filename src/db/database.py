import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the database path
db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'nifty_ai.db')
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

class Signal(Base):
    """Trading signals data model."""
    __tablename__ = 'signals'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    signal_type = Column(String, nullable=False)  # 'CE' or 'PE'
    entry_price = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    tp3 = Column(Float, nullable=False)
    sl = Column(Float, nullable=False)
    status = Column(String, default='active')  # 'active', 'closed'

class Performance(Base):
    """Performance data model."""
    __tablename__ = 'performance'

    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, nullable=False)
    pnl = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    exit_timestamp = Column(DateTime, nullable=False)

def init_db():
    """Initializes the database and creates tables."""
    Base.metadata.create_all(engine)

def get_session():
    """Returns a new database session."""
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == '__main__':
    # Create the database and tables
    init_db()
    print(f'Database initialized at {db_path}')
