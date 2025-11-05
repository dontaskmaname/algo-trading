import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os
import talib
from src.analytics.indicators import get_ohlc_data

def prepare_data(df: pd.DataFrame, future_periods: int = 5) -> tuple:
    """
    Prepares the data for the XGBoost model with advanced feature engineering.

    Args:
        df (pd.DataFrame): The OHLC data.
        future_periods (int): The number of periods to look ahead for the target.

    Returns:
        tuple: A tuple containing the features (X) and target (y).
    """
    # Feature Engineering
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=20).std()

    # TA-Lib Indicators
    df['rsi'] = talib.RSI(df['close'])
    df['macd'], df['macdsignal'], df['macdhist'] = talib.MACD(df['close'])
    df['upper_band'], df['middle_band'], df['lower_band'] = talib.BBANDS(df['close'])

    # Create a more meaningful target variable
    # 1 if the close price in `future_periods` is higher than the current close, 0 otherwise
    df['future_close'] = df['close'].shift(-future_periods)
    df['target'] = (df['future_close'] > df['close']).astype(int)

    # Drop rows with NaN values resulting from feature engineering and target creation
    df.dropna(inplace=True)

    features = [
        'open', 'high', 'low', 'close', 'volume',
        'returns', 'volatility', 'rsi', 'macd',
        'macdsignal', 'macdhist', 'upper_band',
        'middle_band', 'lower_band'
    ]
    X = df[features]
    y = df['target']

    return X, y

def train_model(X: pd.DataFrame, y: pd.Series):
    """
    Trains the XGBoost model.

    Args:
        X (pd.DataFrame): The features.
        y (pd.Series): The target variable.
    """
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        objective='binary:logistic',
        n_estimators=100,
        learning_rate=0.1,
        max_depth=3,
        use_label_encoder=False,
        eval_metric='logloss'
    )

    model.fit(X_train, y_train)

    # Evaluate the model
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model Accuracy: {accuracy:.2f}")

    # Save the model
    model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'xgb_model.json')
    model.save_model(model_path)
    print(f"Model saved to {model_path}")

def get_prediction(X: pd.DataFrame) -> int:
    """
    Gets a prediction from the trained model.

    Args:
        X (pd.DataFrame): The input features for prediction.

    Returns:
        int: The predicted bias (1 for CE, 0 for PE).
    """
    model_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'xgb_model.json')
    if not os.path.exists(model_path):
        return None

    model = xgb.XGBClassifier()
    model.load_model(model_path)

    prediction = model.predict(X.tail(1))
    return prediction[0]

if __name__ == '__main__':
    # Daily retraining pipeline
    symbol = "NIFTY_F1"
    df = get_ohlc_data('1d', 365*5, symbol) # Fetch last 5 years of daily data

    if not df.empty and len(df) > 21: # Need at least 21 days for volatility calculation
        X, y = prepare_data(df)
        train_model(X, y)

        # Get a prediction for the latest data
        prediction = get_prediction(X)
        print(f"Predicted Bias: {'CE' if prediction == 1 else 'PE'}")
    else:
        print("Not enough data to train the model.")
