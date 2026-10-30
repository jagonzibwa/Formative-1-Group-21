import numpy as np
import pandas as pd
import pytest

from src.modeling import prepare_training_frame
from src.preprocessing import FEATURE_COLUMNS, TARGET, WEATHER_CATEGORIES


def make_features(periods: int = 5) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=periods, freq="h")
    frame = pd.DataFrame(0.0, index=index, columns=FEATURE_COLUMNS)
    frame[TARGET] = np.arange(periods, dtype=float)
    for column in ("temp_c", "rain_1h", "snow_1h", "clouds_all"):
        frame[column] = np.arange(periods, dtype=float) + 10
    for category in WEATHER_CATEGORIES:
        frame[f"weather_{category.lower()}"] = 0
    frame["weather_clear"] = 1
    return frame


def test_training_weather_features_only_use_prior_hour():
    prepared = prepare_training_frame(make_features())

    assert prepared.index.tolist() == pd.date_range(
        "2020-01-01 01:00", periods=4, freq="h"
    ).tolist()
    assert prepared.loc[pd.Timestamp("2020-01-01 01:00"), "temp_c"] == 10
    assert prepared.loc[pd.Timestamp("2020-01-01 01:00"), TARGET] == 1


def test_training_rejects_missing_feature_columns():
    frame = make_features().drop(columns=["lag_168"])

    with pytest.raises(ValueError, match="missing required columns"):
        prepare_training_frame(frame)
