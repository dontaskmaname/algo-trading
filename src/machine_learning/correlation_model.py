import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split

def prepare_correlation_data(nifty_df: pd.DataFrame, banknifty_df: pd.DataFrame):
    """
    Prepares data for the correlation model.
    The target variable is the next Nifty move (up or down).
    Features are based on BankNifty's recent behavior.
    """
    # Merge the two dataframes
    df = pd.merge(nifty_df, banknifty_df, on='timestamp', suffixes=('_nifty', '_banknifty'))

    # Feature Engineering for BankNifty
    df['banknifty_return'] = df['close_banknifty'].pct_change()
    df['banknifty_momentum'] = df['banknifty_return'].rolling(window=5).mean()
    df['banknifty_volatility'] = df['banknifty_return'].rolling(window=5).std()

    # Target Variable for Nifty
    df['nifty_target'] = (df['close_nifty'].shift(-1) > df['close_nifty']).astype(int)

    # Drop rows with NaN values
    df.dropna(inplace=True)

    # Define features (X) and target (y)
    features = ['banknifty_return', 'banknifty_momentum', 'banknifty_volatility']
    X = df[features]
    y = df['nifty_target']

    return X, y

def train_correlation_model(X: pd.DataFrame, y: pd.Series):
    """
    Trains the XGBoost model for Nifty-BankNifty correlation.
    """
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        objective='binary:logistic',
        n_estimators=100,
        learning_rate=0.1,
        max_depth=3,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric='logloss'
    )

    model.fit(X_train, y_train, early_stopping_rounds=10, eval_set=[(X_test, y_test)], verbose=False)

    # Save the model
    model.save_model('correlation_model.xgb')
    print("Correlation model trained and saved as correlation_model.xgb")

def get_correlation_prediction(X: pd.DataFrame) -> int:
    """
    Gets a prediction from the trained correlation model.
    """
    model = xgb.XGBClassifier()
    model.load_model('correlation_model.xgb')
    prediction = model.predict(X.tail(1))
    return int(prediction[0])
