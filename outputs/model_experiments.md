| Experiment | Best settings | CV MAE | Test MAE | Test RMSE | Test R² |
|---|---|---:|---:|---:|---:|
| RandomForestRegressor | max_depth=None, min_samples_leaf=3, n_estimators=80 | 182.49 | 150.64 | 240.32 | 0.9850 |
| HistGradientBoostingRegressor | learning_rate=0.1, max_iter=200, max_leaf_nodes=15 | 180.77 | 154.15 | 236.69 | 0.9855 |
| SeasonalNaiveLag168 | forecast=lag_168 | — | 366.37 | 702.20 | 0.8722 |
