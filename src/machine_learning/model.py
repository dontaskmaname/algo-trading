import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os
from src.analytics.indicators import get_ohlc_data

def prepare_data(df: pd.DataFrame) -> tuple:
    """
    Prepares the data for the XGBoost model.

    Args:
        df (pd.DataFrame): The OHLC data.

    Returns:
        tuple: A tuple containing the features (X) and target (y).
    """
    # Feature Engineering
    df['returns'] = df['close'].pct_change()
    df['volatility'] = df['returns'].rolling(window=20).std()

    # Create a synthetic target variable (CE/PE bias)
    # 1 for CE (upward bias), 0 for PE (downward bias)
    df['target'] = (df['close'] > df['close'].shift(1)).astype(int)

    # Drop rows with NaN values resulting from feature engineering
    df.dropna(inplace=True)

    features = ['open', 'high', 'low', 'close', 'volume', 'returns', 'volatility']
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
    df = get_ohlc_data('1d', 60) # Fetch last 60 days of daily data

    if not df.empty and len(df) > 21: # Need at least 21 days for volatility calculation
        X, y = prepare_data(df)
        train_model(X, y)

        # Get a prediction for the latest data
        prediction = get_prediction(X)
        print(f"Predicted Bias: {'CE' if prediction == 1 else 'PE'}")
    else:
        print("Not enough data to train the model.")
