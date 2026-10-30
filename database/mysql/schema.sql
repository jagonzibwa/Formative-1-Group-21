-- =============================================================================
-- Task 2 - Relational schema for the Metro Interstate Traffic Volume dataset
-- Database: MySQL 8.0+
--
-- Why four tables?
--   The raw CSV repeats an hour once per weather condition (48,204 rows for
--   40,575 hours). Traffic is counted once per hour, but the weather station
--   can report several conditions in the same hour (e.g. "Rain" + "Mist").
--   Storing both in one table would duplicate the traffic count, so we split:
--
--     holidays              one row per holiday date
--     weather_conditions    lookup of the 38 (main, description) pairs
--     traffic_readings      one row per hour  -> the time-series target
--     weather_observations  one row per weather report within an hour
--
-- Values are stored as recorded. Invalid sensor readings (0 K temperatures,
-- one 9,831 mm rain value) are kept here and cleaned by src/preprocessing.py,
-- so the database stays a faithful copy of the source data.
--
-- Run:  mysql -u root -p < database/mysql/schema.sql
-- =============================================================================

CREATE DATABASE IF NOT EXISTS metro_traffic
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE metro_traffic;

-- Drop in reverse dependency order so the script can be re-run.
DROP VIEW  IF EXISTS v_hourly_readings;
DROP TABLE IF EXISTS weather_observations;
DROP TABLE IF EXISTS traffic_readings;
DROP TABLE IF EXISTS weather_conditions;
DROP TABLE IF EXISTS holidays;

-- -----------------------------------------------------------------------------
-- holidays: US public holidays (and the Minnesota State Fair) in the dataset.
-- The source only labels the 00:00 row; every hour of that date links here.
-- -----------------------------------------------------------------------------
CREATE TABLE holidays (
    holiday_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    holiday_date  DATE          NOT NULL,
    holiday_name  VARCHAR(50)   NOT NULL,
    PRIMARY KEY (holiday_id),
    UNIQUE KEY uq_holiday_date (holiday_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- weather_conditions: lookup table, e.g. ('Rain', 'light rain').
-- -----------------------------------------------------------------------------
CREATE TABLE weather_conditions (
    condition_id  SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    main          VARCHAR(20)       NOT NULL,
    description   VARCHAR(50)       NOT NULL,
    PRIMARY KEY (condition_id),
    UNIQUE KEY uq_condition (main, description)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- traffic_readings: the time series. One row per hour, unique on date_time.
-- -----------------------------------------------------------------------------
CREATE TABLE traffic_readings (
    reading_id      INT UNSIGNED NOT NULL AUTO_INCREMENT,
    date_time       DATETIME     NOT NULL,          -- local time, start of the hour
    traffic_volume  INT UNSIGNED NOT NULL,          -- westbound vehicles in that hour
    holiday_id      INT UNSIGNED NULL,              -- NULL = ordinary day
    PRIMARY KEY (reading_id),
    UNIQUE KEY uq_reading_time (date_time),         -- one reading per hour; also the date-range index
    KEY idx_reading_holiday (holiday_id),
    CONSTRAINT fk_reading_holiday
        FOREIGN KEY (holiday_id) REFERENCES holidays (holiday_id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT chk_volume CHECK (traffic_volume <= 10000)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- weather_observations: weather reported during an hour (1..n per reading).
-- Deleting a reading deletes its observations.
-- -----------------------------------------------------------------------------
CREATE TABLE weather_observations (
    observation_id  INT UNSIGNED      NOT NULL AUTO_INCREMENT,
    reading_id      INT UNSIGNED      NOT NULL,
    condition_id    SMALLINT UNSIGNED NOT NULL,
    temp            DECIMAL(6,2)      NOT NULL,     -- Kelvin
    rain_1h         DECIMAL(7,2)      NOT NULL DEFAULT 0,   -- mm in the hour
    snow_1h         DECIMAL(5,2)      NOT NULL DEFAULT 0,   -- mm in the hour
    clouds_all      TINYINT UNSIGNED  NOT NULL,     -- % cloud cover
    PRIMARY KEY (observation_id),
    KEY idx_obs_reading (reading_id),
    KEY idx_obs_condition (condition_id),
    CONSTRAINT fk_obs_reading
        FOREIGN KEY (reading_id) REFERENCES traffic_readings (reading_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_obs_condition
        FOREIGN KEY (condition_id) REFERENCES weather_conditions (condition_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_temp   CHECK (temp >= 0),
    CONSTRAINT chk_rain   CHECK (rain_1h >= 0),
    CONSTRAINT chk_snow   CHECK (snow_1h >= 0),
    CONSTRAINT chk_clouds CHECK (clouds_all <= 100)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- v_hourly_readings: one row per hour in the same shape as the API records and
-- the MongoDB documents. Weather values are averaged over the hour's
-- observations (the same rule as clean_raw() in src/preprocessing.py).
-- -----------------------------------------------------------------------------
CREATE VIEW v_hourly_readings AS
SELECT
    r.reading_id,
    r.date_time,
    r.traffic_volume,
    h.holiday_name                         AS holiday,
    ROUND(AVG(o.temp), 2)                  AS temp,
    ROUND(AVG(o.rain_1h), 2)               AS rain_1h,
    ROUND(AVG(o.snow_1h), 2)               AS snow_1h,
    ROUND(AVG(o.clouds_all))               AS clouds_all,
    JSON_ARRAYAGG(JSON_OBJECT('main', c.main, 'description', c.description)) AS weather
FROM traffic_readings r
LEFT JOIN holidays             h ON h.holiday_id   = r.holiday_id
LEFT JOIN weather_observations o ON o.reading_id   = r.reading_id
LEFT JOIN weather_conditions   c ON c.condition_id = o.condition_id
GROUP BY r.reading_id, r.date_time, r.traffic_volume, h.holiday_name;
