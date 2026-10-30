# Time-Series Pipeline — Metro Interstate Traffic Volume (Group 21)

A pipeline for forecasting **hourly traffic on Interstate 94** (Minneapolis–St Paul): exploratory analysis and preprocessing → model training → MySQL and MongoDB storage → a CRUD / time-series API → a prediction script.

## Problem definition
Forecast the **hourly westbound traffic volume** on I-94 at MnDOT ATR station 301. The target is `traffic_volume` (vehicles per hour). The task is a **one-step-ahead regression forecast**: given the traffic history up to hour *t-1*, the calendar and the weather, predict the volume for hour *t*. Short-term traffic forecasts feed ramp metering, incident response, roadwork scheduling and congestion alerts.

## Dataset and why we chose it
[Metro Interstate Traffic Volume](https://www.kaggle.com/datasets/pooriamst/metro-interstate-traffic-volume) (Kaggle; originally UCI ML Repository #492, CC BY 4.0) — 48,204 rows.

| Requirement | How the dataset meets it |
|---|---|
| Clear timestamp | `date_time`, hourly, 2012-10-02 09:00 → 2018-09-30 23:00 |
| Meaningful target | `traffic_volume`, vehicles per hour (0–7,280) |
| Several variables over time | temperature, rain, snow, cloud cover, weather category, holiday |

It also has realistic data problems to solve: duplicate timestamps, 22.8% missing hours (including a 10-month outage) and impossible sensor values.

---

## Task 1A — Understanding the dataset
Notebook: [`notebooks/01_eda_preprocessing.ipynb`](notebooks/01_eda_preprocessing.ipynb)

* **Time range:** 2 Oct 2012 – 30 Sep 2018 (≈ 6 years). **Granularity:** hourly.
* **Duplicates:** 7,629 rows share a timestamp. Traffic is identical within each hour; only the weather condition differs. They are collapsed to one row per hour, keeping the most severe condition.
* **Missing values:** 11,976 of 52,551 expected hours (22.8%) are missing. Most gaps are 1 hour; one outage runs from 8 Aug 2014 to 11 Jun 2015.

| Problem | Method | Why |
|---|---|---|
| Holiday only labelled at 00:00 | Spread to all 24 hours of the date, add `is_holiday` | A holiday is a property of the day |
| Gaps ≤ 3 h | Time-based linear interpolation, flagged `is_imputed` | Traffic changes smoothly over 1–3 h; keeps lag features correct |
| Gaps > 3 h (incl. the 10-month outage) | Not filled; affected lag windows dropped | Filling would invent daily and weekly cycles |
| 0 K temperatures, 9,831 mm rain | Set to NaN, then handled as missing | Physically impossible readings |

* **Distributions:** traffic is bimodal (night ≈ 300–1,000, day ≈ 4,500–6,000 vehicles/h); rain and snow are zero-inflated and heavily skewed; cloud cover is U-shaped.

The cleaning code is in [`src/preprocessing.py`](src/preprocessing.py) so later stages (training, prediction) can reuse exactly the same steps.

## Task 1B — Analytical questions
Each question has at least one chart (in [`outputs/figures/`](outputs/figures/)) and an interpretation in the notebook. **Q1, Q3 and Q6 use moving averages and/or lagged features.**

| # | Question | Main finding |
|---|---|---|
| Q1 | Is there a long-term trend? *(7/30/365-day moving averages)* | No meaningful trend (+0.44%/year, p = 0.055); strong seasonality |
| Q2 | What daily and weekly patterns exist? | Weekday peaks at 07:00 and 16:00; weekends 26% lower |
| Q3 | Are there lag effects? *(lagged features, ACF/PACF)* | Lag 168 h r = 0.946 (strongest), lag 1 h r = 0.915 |
| Q4 | Do weather variables correlate with traffic? | Snow cuts rush-hour traffic by 12%; other weather effects are small |
| Q5 | How do holidays change traffic? | −27% on average; up to −49% on Christmas / New Year |
| Q6 | Do moving averages show whether this hour will be above or below last week? *(lags + moving averages)* | Yes, r = 0.47; MA-adjusted weekly forecast is 6.4% more accurate |

---

## Repository structure (current)
```
├── data/
│   ├── raw/Metro_Interstate_Traffic_Volume.csv.gz      original dataset
│   └── processed/traffic_hourly_clean.csv.gz           cleaned, feature-ready data (written by notebook 01)
├── notebooks/01_eda_preprocessing.ipynb                Task 1A/B
├── src/
│   ├── preprocessing.py                                cleaning + feature pipeline
│   ├── plotting.py                                     chart style
│   └── config.py                                       project paths and settings
└── outputs/figures/                                    EDA charts
```

## Running it
```bash
pip install -r requirements.txt
```
```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda_preprocessing.ipynb
```

## Project parts

| Part | Status |
|---|---|
| Task 1A/B — EDA, preprocessing, analytical questions | ✅ in this repository |
| Task 1C — Model training and experiments | to be added |
| Task 2 — SQL and MongoDB databases | to be added |
| Task 3 — CRUD and time-series API | to be added |
| Task 4 — Prediction script | to be added |

## Data source
Hogue, J. (2019). *Metro Interstate Traffic Volume* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5X60B — CC BY 4.0.
