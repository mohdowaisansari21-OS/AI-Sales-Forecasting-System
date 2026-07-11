import numpy as np
import joblib
from preprocess import fetch_data
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

# 1. Fetch data (now from sales_data.csv, aggregated by day)
df = fetch_data()

# 2. Create feature: day index 0, 1, 2, ... in date order
df["day"] = np.arange(len(df))

X = df[["day"]]
y = df["sales"]

# 3. Train model
model = LinearRegression()
model.fit(X, y)

# 4. Predict on training data (check working)
y_pred = model.predict(X)

# 5. Evaluate
mae = mean_absolute_error(y, y_pred)
r2 = r2_score(y, y_pred)

print("Model training completed")
print("Mean Absolute Error:", mae)
print("R2 Score:", r2)

# 6. Save model + metadata needed to continue the day/date sequence later.
#    api_server.py and forecast.py/predict.py load this same bundle so
#    everything stays consistent with what the model was actually trained on.
bundle = {
    "model": model,
    "last_day": int(df["day"].iloc[-1]),
    "last_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
    "trained_rows": len(df),
}
joblib.dump(bundle, "sales_model.pkl")
print(f"Model trained and saved successfully (last_day={bundle['last_day']}, last_date={bundle['last_date']})")
