import pandas as pd
import numpy as np
import joblib

bundle = joblib.load("sales_model.pkl")
model = bundle["model"]
last_day = bundle["last_day"]
last_date = pd.to_datetime(bundle["last_date"])

future_days = 10

future_X = pd.DataFrame(
    np.arange(last_day + 1, last_day + 1 + future_days),
    columns=["day"],
)
predictions = np.maximum(0, model.predict(future_X))
future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, future_days + 1)]

future = pd.DataFrame({
    "date": [d.strftime("%Y-%m-%d") for d in future_dates],
    "day": future_X["day"],
    "forecast_sales": predictions.round(2),
})

future.to_csv("forecast_output.csv", index=False)
print("Forecast generated")
print(future)
