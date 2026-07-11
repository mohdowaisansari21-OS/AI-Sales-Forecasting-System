import pandas as pd
import numpy as np
import joblib

# Load trained model bundle (model + where its day/date sequence left off)
bundle = joblib.load("sales_model.pkl")
model = bundle["model"]
last_day = bundle["last_day"]
last_date = pd.to_datetime(bundle["last_date"])

# Number of future days to predict
future_days = 5

future_X = pd.DataFrame(
    np.arange(last_day + 1, last_day + 1 + future_days),
    columns=["day"],
)

# Predict future sales
predictions = np.maximum(0, model.predict(future_X))

# Attach real calendar dates, continuing from the last training date
future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, future_days + 1)]

result = pd.DataFrame({
    "date": [d.strftime("%Y-%m-%d") for d in future_dates],
    "day": future_X["day"],
    "predicted_sales": predictions.round(2),
})

result.to_csv("future_sales_predictions.csv", index=False)

print("Future sales prediction completed")
print(result)
