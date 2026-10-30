"""Task 2 - MongoDB queries on metro_traffic.traffic_readings.

The same five questions as database/mysql/queries.sql, answered with find()
and aggregation pipelines. scripts/run_queries.py runs them and saves the
results to outputs/query_results/.

Each entry: id -> (question, kind, spec)
    kind "find":      spec = {"filter", "projection", "sort", "limit"}
    kind "aggregate": spec = pipeline (list of stages)
"""
from datetime import datetime

RUSH_HOURS = [7, 8, 16, 17]

MONGO_QUERIES = {
    # Q1. Latest record: newest 5 hours (uses the unique date_time index).
    "mongo_q1_latest_records": (
        "Latest record: the 5 most recent hours",
        "find",
        {
            "filter": {},
            "projection": {"_id": 0, "date_time": 1, "traffic_volume": 1,
                           "holiday": 1, "temp": 1, "weather.description": 1},
            "sort": [("date_time", -1)],
            "limit": 5,
        },
    ),

    # Q2. Records by date range: daily totals for 24-30 Sep 2018.
    "mongo_q2_date_range_daily": (
        "Records by date range: daily totals, 24-30 Sep 2018",
        "aggregate",
        [
            {"$match": {"date_time": {"$gte": datetime(2018, 9, 24),
                                      "$lt": datetime(2018, 10, 1)}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_time"}},
                "hours_recorded": {"$sum": 1},
                "total_vehicles": {"$sum": "$traffic_volume"},
                "avg_per_hour": {"$avg": "$traffic_volume"},
                "peak_hour_volume": {"$max": "$traffic_volume"},
            }},
            {"$sort": {"_id": 1}},
            {"$project": {"_id": 0, "day": "$_id", "hours_recorded": 1, "total_vehicles": 1,
                          "avg_per_hour": {"$round": ["$avg_per_hour", 0]},
                          "peak_hour_volume": 1}},
        ],
    ),

    # Q3. Weekday rush-hour traffic by weather category ($unwind the embedded array).
    "mongo_q3_weather_rush_hour": (
        "Weekday rush-hour (07-08, 16-17) traffic by weather category, non-holidays",
        "aggregate",
        [
            {"$match": {"holiday": None}},
            {"$addFields": {"hour": {"$hour": "$date_time"},
                            "dow": {"$dayOfWeek": "$date_time"}}},   # 1 = Sunday
            {"$match": {"hour": {"$in": RUSH_HOURS}, "dow": {"$gte": 2, "$lte": 6}}},
            {"$unwind": "$weather"},
            # count each hour once per weather category
            {"$group": {"_id": {"main": "$weather.main", "hour_id": "$_id"},
                        "volume": {"$first": "$traffic_volume"}}},
            {"$group": {"_id": "$_id.main", "rush_hours": {"$sum": 1},
                        "avg_volume": {"$avg": "$volume"}}},
            {"$match": {"rush_hours": {"$gte": 30}}},
            {"$project": {"_id": 0, "weather": "$_id", "rush_hours": 1,
                          "avg_volume": {"$round": ["$avg_volume", 0]}}},
            {"$sort": {"avg_volume": -1}},
        ],
    ),

    # Q4. Holiday effect: average daily traffic over complete (24-hour) days.
    "mongo_q4_holiday_effect": (
        "Average daily traffic on holidays vs ordinary weekdays (complete days only)",
        "aggregate",
        [
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_time"}},
                "holiday": {"$first": "$holiday"},
                "dow": {"$first": {"$dayOfWeek": "$date_time"}},
                "hours": {"$sum": 1},
                "vehicles": {"$sum": "$traffic_volume"},
            }},
            {"$match": {"hours": 24,
                        "$or": [{"holiday": {"$ne": None}}, {"dow": {"$gte": 2, "$lte": 6}}]}},
            {"$group": {"_id": {"$ifNull": ["$holiday", "(ordinary weekday)"]},
                        "complete_days": {"$sum": 1},
                        "avg_daily_vehicles": {"$avg": "$vehicles"}}},
            {"$project": {"_id": 0, "day_type": "$_id", "complete_days": 1,
                          "avg_daily_vehicles": {"$round": ["$avg_daily_vehicles", 0]}}},
            {"$sort": {"avg_daily_vehicles": -1}},
        ],
    ),

    # Q5. Lag and moving-average features with $setWindowFields (MongoDB 5.0+).
    "mongo_q5_lag_moving_average": (
        "Lag-1, lag-24 and 24-hour moving average, 30 Sep 2018 from 06:00",
        "aggregate",
        [
            {"$match": {"date_time": {"$gte": datetime(2018, 9, 28)}}},
            {"$setWindowFields": {
                "sortBy": {"date_time": 1},
                "output": {
                    "lag_1h": {"$shift": {"output": "$traffic_volume", "by": -1}},
                    "lag_24h": {"$shift": {"output": "$traffic_volume", "by": -24}},
                    "ma_24h": {"$avg": "$traffic_volume",
                               "window": {"documents": [-24, -1]}},
                },
            }},
            {"$match": {"date_time": {"$gte": datetime(2018, 9, 30, 6)}}},
            {"$sort": {"date_time": 1}},
            {"$limit": 12},
            {"$project": {"_id": 0, "date_time": 1, "traffic_volume": 1, "lag_1h": 1,
                          "lag_24h": 1, "ma_24h": {"$round": ["$ma_24h", 0]}}},
        ],
    ),
}
