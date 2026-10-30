"""Model training helpers shared by the training script and tests."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

from src.preprocessing import FEATURE_COLUMNS, TARGET, WEATHER_CATEGORIES

WEATHER_FEATURE_COLUMNS = [
    "temp_c",
    "rain_1h",
    "snow_1h",
    "clouds_all",
    *(f"weather_{category.lower()}" for category in WEATHER_CATEGORIES),
]


def prepare_training_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Align weather inputs to information available before each forecast hour."""
    if not isinstance(features.index, pd.DatetimeIndex):
        raise ValueError("Training features must use a DatetimeIndex.")
    if features.index.has_duplicates:
        raise ValueError("Training features contain duplicate timestamps.")

    missing = sorted(set(FEATURE_COLUMNS + [TARGET]) - set(features.columns))
    if missing:
        raise ValueError(f"Training data is missing required columns: {missing}")

    ordered = features.sort_index()
    x = ordered.loc[:, FEATURE_COLUMNS].copy()
    x[WEATHER_FEATURE_COLUMNS] = x[WEATHER_FEATURE_COLUMNS].astype(float).shift(1)
    y = pd.to_numeric(ordered[TARGET], errors="coerce")

    valid = x.notna().all(axis=1) & y.notna() & np.isfinite(y)
    prepared = x.loc[valid].copy()
    prepared[TARGET] = y.loc[valid]
    return prepared


def experiment_searches(random_state: int = 42) -> list[tuple[str, Any, dict[str, list[Any]]]]:
    """Return two tuned, complementary tree-based regression experiments."""
    random_forest = RandomForestRegressor(
        random_state=random_state,
        n_jobs=-1,
    )
    histogram_gradient_boosting = HistGradientBoostingRegressor(
        random_state=random_state,
    )
    return [
        (
            "RandomForestRegressor",
            random_forest,
            {
                "n_estimators": [80],
                "max_depth": [12, None],
                "min_samples_leaf": [1, 3],
            },
        ),
        (
            "HistGradientBoostingRegressor",
            histogram_gradient_boosting,
            {
                "learning_rate": [0.05, 0.1],
                "max_iter": [100, 200],
                "max_leaf_nodes": [15],
            },
        ),
    ]


def tune_experiments(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    cv_splits: int = 3,
    random_state: int = 42,
) -> list[dict[str, Any]]:
    """Tune each model with forward-chaining CV, returning fitted search results."""
    if len(x_train) <= cv_splits:
        raise ValueError("Not enough training rows for the requested time-series CV.")

    time_cv = TimeSeriesSplit(n_splits=cv_splits)
    results = []
    for name, estimator, parameter_grid in experiment_searches(random_state):
        search = GridSearchCV(
            estimator=estimator,
            param_grid=parameter_grid,
            scoring="neg_mean_absolute_error",
            cv=time_cv,
            n_jobs=1,
            refit=True,
            error_score="raise",
        )
        search.fit(x_train, y_train)
        results.append(
            {
                "name": name,
                "best_params": search.best_params_,
                "cv_mae": -float(search.best_score_),
                "model": search.best_estimator_,
            }
        )
    return results
