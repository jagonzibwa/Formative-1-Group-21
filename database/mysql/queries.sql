-- =============================================================================
-- Task 2 - MySQL queries on metro_traffic
-- Each query starts with "-- name: <id>" so scripts/run_queries.py can run it
-- and save its result to outputs/query_results/.
-- =============================================================================

-- name: sql_q1_latest_records
-- Q1. Latest record: the 5 most recent hours with holiday and weather (3-table join).
SELECT r.date_time,
       r.traffic_volume,
       COALESCE(h.holiday_name, '-')                              AS holiday,
       ROUND(AVG(o.temp) - 273.15, 1)                             AS temp_c,
       GROUP_CONCAT(DISTINCT c.description ORDER BY c.description SEPARATOR ', ') AS weather
FROM traffic_readings r
LEFT JOIN holidays             h ON h.holiday_id   = r.holiday_id
JOIN      weather_observations o ON o.reading_id   = r.reading_id
JOIN      weather_conditions   c ON c.condition_id = o.condition_id
GROUP BY r.reading_id, r.date_time, r.traffic_volume, h.holiday_name
ORDER BY r.date_time DESC
LIMIT 5;

-- name: sql_q2_date_range_daily
-- Q2. Records by date range: daily totals for the last week of the dataset
--     (uses the unique index on date_time).
SELECT DATE(date_time)                AS day,
       DAYNAME(date_time)             AS weekday,
       COUNT(*)                       AS hours_recorded,
       SUM(traffic_volume)            AS total_vehicles,
       ROUND(AVG(traffic_volume))     AS avg_per_hour,
       MAX(traffic_volume)            AS peak_hour_volume
FROM traffic_readings
WHERE date_time >= '2018-09-24 00:00:00'
  AND date_time <  '2018-10-01 00:00:00'
GROUP BY DATE(date_time), DAYNAME(date_time)
ORDER BY day;

-- name: sql_q3_weather_rush_hour
-- Q3. How does weather change weekday rush-hour traffic (07:00-08:00, 16:00-17:00)?
--     Hours with several reports are counted once per weather category.
SELECT c.main                              AS weather,
       COUNT(DISTINCT r.reading_id)        AS rush_hours,
       ROUND(AVG(r.traffic_volume))        AS avg_volume
FROM traffic_readings r
JOIN weather_observations o ON o.reading_id   = r.reading_id
JOIN weather_conditions   c ON c.condition_id = o.condition_id
WHERE HOUR(r.date_time) IN (7, 8, 16, 17)
  AND WEEKDAY(r.date_time) < 5
  AND r.holiday_id IS NULL
GROUP BY c.main
HAVING rush_hours >= 30
ORDER BY avg_volume DESC;

-- name: sql_q4_holiday_effect
-- Q4. Average daily traffic on each holiday compared with ordinary weekdays.
--     Only complete days (all 24 hours recorded) are used, so gaps in the data
--     do not pull a day's total down.
WITH daily AS (
    SELECT DATE(date_time)      AS day,
           holiday_id,
           SUM(traffic_volume)  AS vehicles
    FROM traffic_readings
    GROUP BY DATE(date_time), holiday_id
    HAVING COUNT(*) = 24
)
SELECT COALESCE(h.holiday_name, '(ordinary weekday)') AS day_type,
       COUNT(*)                                       AS complete_days,
       ROUND(AVG(d.vehicles))                         AS avg_daily_vehicles
FROM daily d
LEFT JOIN holidays h ON h.holiday_id = d.holiday_id
WHERE d.holiday_id IS NOT NULL OR WEEKDAY(d.day) < 5
GROUP BY h.holiday_name
ORDER BY avg_daily_vehicles DESC;

-- name: sql_q5_lag_moving_average
-- Q5. Time-series window functions: lag-1, lag-24 and a 24-hour moving average
--     for the last day in the dataset (the features used in Task 1).
--     LAG counts rows, not hours, so it is only valid where no hours are
--     missing; 28-30 Sep 2018 is complete (72 of 72 hours).
SELECT date_time,
       traffic_volume,
       lag_1h,
       lag_24h,
       ma_24h
FROM (
    SELECT date_time,
           traffic_volume,
           LAG(traffic_volume, 1)  OVER w                                   AS lag_1h,
           LAG(traffic_volume, 24) OVER w                                   AS lag_24h,
           ROUND(AVG(traffic_volume) OVER (w ROWS BETWEEN 24 PRECEDING AND 1 PRECEDING)) AS ma_24h
    FROM traffic_readings
    WHERE date_time >= '2018-09-28 00:00:00'
    WINDOW w AS (ORDER BY date_time)
) t
WHERE date_time >= '2018-09-30 06:00:00'
ORDER BY date_time
LIMIT 12;
