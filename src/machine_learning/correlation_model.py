import pandas as pd
import talib
import xgboost as xgb
import os

# Define the path for the saved model
MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'correlation_model.json')

# Ensure the model directory exists
os.makedirs(MODEL_DIR, exist_ok=True)

def prepare_correlation_data(nifty_df: pd.DataFrame, banknifty_df: pd.DataFrame):
    """
    Prepares data for the Nifty-BankNifty correlation model by creating features.
    """
    if nifty_df.empty or banknifty_df.empty:
        return pd.DataFrame(), pd.Series(name="target")

    # Combine the two dataframes
    df = pd.merge(nifty_df, banknifty_df, on='timestamp', suffixes=('_nifty', '_bn'))

    # Feature Engineering
    df['nifty_returns'] = df['close_nifty'].pct_change()
    df['bn_returns'] = df['close_bn'].pct_change()

    # Rolling correlation
    df['rolling_corr'] = df['nifty_returns'].rolling(window=14).corr(df['bn_returns'])

    # RSI
    df['rsi_nifty'] = talib.RSI(df['close_nifty'], timeperiod=14)
    df['rsi_bn'] = talib.RSI(df['close_bn'], timeperiod=14)

    # Price difference
    df['price_diff'] = df['close_nifty'] - df['close_bn']

    # Target variable: 1 if Nifty goes up in 5 periods, 0 otherwise
    df['target'] = (df['close_nifty'].shift(-5) > df['close_nifty']).astype(int)

    # Drop rows with NaN values
    df.dropna(inplace=True)

    if df.empty:
        return pd.DataFrame(), pd.Series(name="target")

    # Define features (X) and target (y)
    features = ['rolling_corr', 'rsi_nifty', 'rsi_bn', 'price_diff', 'bn_returns']
    X = df[features]
    y = df['target']

    return X, y

def get_correlation_prediction(X: pd.DataFrame):
    """
    Returns a prediction from the Nifty-BankNifty correlation model.
    """
    if not os.path.exists(MODEL_PATH) or X.empty:
        return 1  # Default to 'CE' if no model or data

    model = xgb.XGBClassifier()
    model.load_model(MODEL_PATH)

    # Predict the probability of the positive class (1)
    prediction_proba = model.predict_proba(X.tail(1))

    # Return the class with the highest probability
    return prediction_proba.argmax()


def train_correlation_model(X: pd.DataFrame, y: pd.Series):
    """
    Trains the Nifty-BankNifty correlation model.
    """
    if X.empty or y.empty:
        print("Cannot train correlation model: No data provided.")
        return

    model = xgb.XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        use_label_encoder=False,
        n_estimators=100,
        learning_rate=0.1,
        max_depth=3,
        subsample=0.8,
        colsample_bytree=0.8,
    )
    model.fit(X, y)
    model.save_model(MODEL_PATH)
    print(f"Correlation model trained and saved to {MODEL_PATH}")
