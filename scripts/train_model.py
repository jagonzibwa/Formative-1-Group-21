"""Tune traffic forecasting models and save the best model and evaluation results."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import (  # noqa: E402
    MODEL_METADATA_PATH,
    MODEL_PATH,
    RAW_DATA_PATH,
)
from src.modeling import prepare_training_frame, tune_experiments  # noqa: E402
from src.preprocessing import FEATURE_COLUMNS, TARGET, load_raw, preprocess  # noqa: E402


def _markdown_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Experiment | Best settings | CV MAE | Test MAE | Test RMSE | Test R² |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for result in results:
        settings = ", ".join(
            f"{key}={value}" for key, value in result["best_params"].items()
        ) or "baseline"
        metrics = result["test_metrics"]
        cv_mae = result["cv_mae"]
        cv_text = f"{cv_mae:.2f}" if cv_mae is not None else "—"
        lines.append(
            f"| {result['name']} | {settings} | "
            f"{cv_text} | "
            f"{metrics['mae']:.2f} | {metrics['rmse']:.2f} | {metrics['r2']:.4f} |"
        )
    return "\n".join(lines) + "\n"


def train(
    raw_data_path: Path = RAW_DATA_PATH,
    *,
    model_path: Path = MODEL_PATH,
    metadata_path: Path = MODEL_METADATA_PATH,
    test_fraction: float = 0.2,
    cv_splits: int = 3,
    random_state: int = 42,
) -> dict[str, Any]:
    """Fit two tuned models on past data, compare on a later holdout, and save."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1.")
    if not raw_data_path.is_file():
        raise FileNotFoundError(f"Raw dataset was not found: {raw_data_path}")

    raw = load_raw(raw_data_path)
    features = preprocess(raw, dropna=False)
    prepared = prepare_training_frame(features)
    if len(prepared) < 100:
        raise ValueError(f"Only {len(prepared)} usable rows; at least 100 are required.")

    split_at = int(len(prepared) * (1 - test_fraction))
    if split_at <= cv_splits:
        raise ValueError("Training split is too small for the requested CV folds.")
    train_rows, test_rows = prepared.iloc[:split_at], prepared.iloc[split_at:]
    x_train, y_train = train_rows[FEATURE_COLUMNS], train_rows[TARGET]
    x_test, y_test = test_rows[FEATURE_COLUMNS], test_rows[TARGET]

    experiments = tune_experiments(
        x_train,
        y_train,
        cv_splits=cv_splits,
        random_state=random_state,
    )
    results = []
    for experiment in experiments:
        predictions = experiment["model"].predict(x_test)
        results.append(
            {
                "name": experiment["name"],
                "best_params": experiment["best_params"],
                "cv_mae": experiment["cv_mae"],
                "test_metrics": {
                    "mae": float(mean_absolute_error(y_test, predictions)),
                    "rmse": math.sqrt(mean_squared_error(y_test, predictions)),
                    "r2": float(r2_score(y_test, predictions)),
                },
            }
        )

    baseline_prediction = test_rows["lag_168"]
    results.append(
        {
            "name": "SeasonalNaiveLag168",
            "best_params": {"forecast": "lag_168"},
            "cv_mae": None,
            "test_metrics": {
                "mae": float(mean_absolute_error(y_test, baseline_prediction)),
                "rmse": math.sqrt(mean_squared_error(y_test, baseline_prediction)),
                "r2": float(r2_score(y_test, baseline_prediction)),
            },
        }
    )

    best_index = min(
        range(len(experiments)),
        key=lambda index: experiments[index]["cv_mae"],
    )
    selected = experiments[best_index]
    selected_result = results[best_index]

    # Keep the holdout untouched for evaluation; only after scoring is complete
    # refit the CV-selected model on all observations for deployment.
    selected["model"].fit(prepared[FEATURE_COLUMNS], prepared[TARGET])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected["model"], model_path, compress=3)

    metadata = {
        "target": TARGET,
        # Keep the aliases consumed by Task 4's API prediction script.
        "model": selected["name"],
        "experiment": selected["name"],
        "features": FEATURE_COLUMNS,
        "selected_model": selected["name"],
        "best_params": selected["best_params"],
        "feature_columns": FEATURE_COLUMNS,
        "training_rows": len(prepared),
        "selection_train_start": train_rows.index.min().isoformat(),
        "selection_train_end": train_rows.index.max().isoformat(),
        "model_selection": "lowest cross-validation MAE on the training period",
        "holdout_used_for_model_selection": False,
        "test_rows": len(test_rows),
        "training_start": prepared.index.min().isoformat(),
        "training_end": prepared.index.max().isoformat(),
        "test_start": test_rows.index.min().isoformat(),
        "test_end": test_rows.index.max().isoformat(),
        "weather_feature_policy": (
            "Weather predictors are shifted one hour so only the latest observed "
            "weather is used for a one-step-ahead forecast."
        ),
        "cross_validation": {
            "method": "TimeSeriesSplit",
            "n_splits": cv_splits,
            "scoring": "negative mean absolute error",
        },
        "experiments": results,
        "selected_test_metrics": selected_result["test_metrics"],
        "test_metrics": {
            "test_mae": selected_result["test_metrics"]["mae"],
            "test_rmse": selected_result["test_metrics"]["rmse"],
            "test_r2": selected_result["test_metrics"]["r2"],
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    results_path = ROOT_DIR / "outputs" / "model_experiments.csv"
    pd.DataFrame(
        [
            {
                "experiment": result["name"],
                "best_params": json.dumps(result["best_params"], sort_keys=True),
                "cv_mae": result["cv_mae"],
                **result["test_metrics"],
            }
            for result in results
        ]
    ).to_csv(results_path, index=False)
    markdown_path = ROOT_DIR / "outputs" / "model_experiments.md"
    markdown_path.write_text(_markdown_table(results), encoding="utf-8")

    print(f"Selected model: {selected['name']}")
    print(f"Saved model: {model_path}")
    print(f"Saved metadata: {metadata_path}")
    print(f"Saved experiment results: {markdown_path}")
    print(_markdown_table(results))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=RAW_DATA_PATH)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--cv-splits", type=int, default=3)
    args = parser.parse_args()
    train(
        raw_data_path=args.data,
        test_fraction=args.test_fraction,
        cv_splits=args.cv_splits,
    )


if __name__ == "__main__":
    main()
