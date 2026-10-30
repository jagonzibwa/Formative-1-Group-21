# API test results

_Generated 2026-10-26 14:44 by `scripts/test_api.py` against http://127.0.0.1:8000. Failures: 0._
### PASS `GET /` -> 200 (expected 200)

Response:
```json
{
  "api": "ok",
  "mysql_records": 40575,
  "mongodb_records": 40575
}
```


## `/sql` endpoints

### PASS `POST /sql/records` -> 201 (expected 201)

Body:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ]
}
```

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ],
  "id": 40578
}
```

### PASS `POST /sql/records` -> 409 (expected 409)

Body:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ]
}
```

Response:
```json
{
  "detail": "A record for 2018-10-01 00:00:00 already exists"
}
```

### PASS `GET /sql/records/40578` -> 200 (expected 200)

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ],
  "id": 40578
}
```

### PASS `GET /sql/records/latest` -> 200 (expected 200)

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ],
  "id": 40578
}
```

### PASS `GET /sql/records/range?start=2018-09-30T20:00:00&end=2018-10-01T00:00:00` -> 200 (expected 200)

Response:
```json
{
  "count": 5,
  "records": [
    {
      "date_time": "2018-09-30T20:00:00",
      "traffic_volume": 2781,
      "temp": 282.76,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Clouds",
          "description": "overcast clouds"
        }
      ],
      "id": 40572
    },
    {
      "date_time": "2018-09-30T21:00:00",
      "traffic_volume": 2159,
      "temp": 282.73,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Thunderstorm",
          "description": "proximity thunderstorm"
        }
      ],
      "id": 40573
    },
    {
      "date_time": "2018-09-30T22:00:00",
      "traffic_volume": 1450,
      "temp": 282.09,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Clouds",
          "description": "overcast clouds"
        }
      ],
      "id": 40574
    },
    "... 2 more"
  ]
}
```

### PASS `GET /sql/records/range?start=2018-10-02T00:00:00&end=2018-10-01T00:00:00` -> 400 (expected 400)

Response:
```json
{
  "detail": "start must be <= end"
}
```

### PASS `PUT /sql/records/40578` -> 200 (expected 200)

Body:
```json
{
  "traffic_volume": 655,
  "clouds_all": 90,
  "weather": [
    {
      "main": "Rain",
      "description": "light rain"
    },
    {
      "main": "Mist",
      "description": "mist"
    }
  ]
}
```

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 655,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 90,
  "holiday": null,
  "weather": [
    {
      "main": "Rain",
      "description": "light rain"
    },
    {
      "main": "Mist",
      "description": "mist"
    }
  ],
  "id": 40578
}
```

### PASS `PUT /sql/records/40578` -> 422 (expected 422)

Body:
```json
{
  "clouds_all": 150
}
```

Response:
```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": [
        "body",
        "clouds_all"
      ],
      "msg": "Input should be less than or equal to 100",
      "input": 150,
      "ctx": {
        "le": 100
      }
    }
  ]
}
```

### PASS `GET /sql/records?limit=2` -> 200 (expected 200)

Response:
```json
{
  "count": 2,
  "records": [
    {
      "date_time": "2018-10-01T00:00:00",
      "traffic_volume": 655,
      "temp": 281.4,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Rain",
          "description": "light rain"
        },
        {
          "main": "Mist",
          "description": "mist"
        }
      ],
      "id": 40578
    },
    {
      "date_time": "2018-09-30T23:00:00",
      "traffic_volume": 954,
      "temp": 282.12,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Clouds",
          "description": "overcast clouds"
        }
      ],
      "id": 40575
    }
  ]
}
```

### PASS `DELETE /sql/records/40578` -> 200 (expected 200)

Response:
```json
{
  "deleted": true,
  "record": {
    "date_time": "2018-10-01T00:00:00",
    "traffic_volume": 655,
    "temp": 281.4,
    "rain_1h": 0.0,
    "snow_1h": 0.0,
    "clouds_all": 90,
    "holiday": null,
    "weather": [
      {
        "main": "Rain",
        "description": "light rain"
      },
      {
        "main": "Mist",
        "description": "mist"
      }
    ],
    "id": 40578
  }
}
```

### PASS `GET /sql/records/40578` -> 404 (expected 404)

Response:
```json
{
  "detail": "Record 40578 not found"
}
```


## `/mongo` endpoints

### PASS `POST /mongo/records` -> 201 (expected 201)

Body:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ]
}
```

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ],
  "id": "6adf4b20c09ec4df5610bb7b"
}
```

### PASS `POST /mongo/records` -> 409 (expected 409)

Body:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ]
}
```

Response:
```json
{
  "detail": "A record for that date_time already exists"
}
```

### PASS `GET /mongo/records/6adf4b20c09ec4df5610bb7b` -> 200 (expected 200)

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ],
  "id": "6adf4b20c09ec4df5610bb7b"
}
```

### PASS `GET /mongo/records/latest` -> 200 (expected 200)

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 612,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 75,
  "holiday": null,
  "weather": [
    {
      "main": "Clouds",
      "description": "broken clouds"
    }
  ],
  "id": "6adf4b20c09ec4df5610bb7b"
}
```

### PASS `GET /mongo/records/range?start=2018-09-30T20:00:00&end=2018-10-01T00:00:00` -> 200 (expected 200)

Response:
```json
{
  "count": 5,
  "records": [
    {
      "date_time": "2018-09-30T20:00:00",
      "traffic_volume": 2781,
      "temp": 282.76,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Clouds",
          "description": "overcast clouds"
        }
      ],
      "id": "6adf49388b5edaeb3c09dd93"
    },
    {
      "date_time": "2018-09-30T21:00:00",
      "traffic_volume": 2159,
      "temp": 282.73,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Thunderstorm",
          "description": "proximity thunderstorm"
        }
      ],
      "id": "6adf49388b5edaeb3c09dd94"
    },
    {
      "date_time": "2018-09-30T22:00:00",
      "traffic_volume": 1450,
      "temp": 282.09,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Clouds",
          "description": "overcast clouds"
        }
      ],
      "id": "6adf49388b5edaeb3c09dd95"
    },
    "... 2 more"
  ]
}
```

### PASS `GET /mongo/records/range?start=2018-10-02T00:00:00&end=2018-10-01T00:00:00` -> 400 (expected 400)

Response:
```json
{
  "detail": "start must be <= end"
}
```

### PASS `PUT /mongo/records/6adf4b20c09ec4df5610bb7b` -> 200 (expected 200)

Body:
```json
{
  "traffic_volume": 655,
  "clouds_all": 90,
  "weather": [
    {
      "main": "Rain",
      "description": "light rain"
    },
    {
      "main": "Mist",
      "description": "mist"
    }
  ]
}
```

Response:
```json
{
  "date_time": "2018-10-01T00:00:00",
  "traffic_volume": 655,
  "temp": 281.4,
  "rain_1h": 0.0,
  "snow_1h": 0.0,
  "clouds_all": 90,
  "holiday": null,
  "weather": [
    {
      "main": "Rain",
      "description": "light rain"
    },
    {
      "main": "Mist",
      "description": "mist"
    }
  ],
  "id": "6adf4b20c09ec4df5610bb7b"
}
```

### PASS `PUT /mongo/records/6adf4b20c09ec4df5610bb7b` -> 422 (expected 422)

Body:
```json
{
  "clouds_all": 150
}
```

Response:
```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": [
        "body",
        "clouds_all"
      ],
      "msg": "Input should be less than or equal to 100",
      "input": 150,
      "ctx": {
        "le": 100
      }
    }
  ]
}
```

### PASS `GET /mongo/records?limit=2` -> 200 (expected 200)

Response:
```json
{
  "count": 2,
  "records": [
    {
      "date_time": "2018-10-01T00:00:00",
      "traffic_volume": 655,
      "temp": 281.4,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Rain",
          "description": "light rain"
        },
        {
          "main": "Mist",
          "description": "mist"
        }
      ],
      "id": "6adf4b20c09ec4df5610bb7b"
    },
    {
      "date_time": "2018-09-30T23:00:00",
      "traffic_volume": 954,
      "temp": 282.12,
      "rain_1h": 0.0,
      "snow_1h": 0.0,
      "clouds_all": 90,
      "holiday": null,
      "weather": [
        {
          "main": "Clouds",
          "description": "overcast clouds"
        }
      ],
      "id": "6adf49388b5edaeb3c09dd96"
    }
  ]
}
```

### PASS `DELETE /mongo/records/6adf4b20c09ec4df5610bb7b` -> 200 (expected 200)

Response:
```json
{
  "deleted": true,
  "record": {
    "date_time": "2018-10-01T00:00:00",
    "traffic_volume": 655,
    "temp": 281.4,
    "rain_1h": 0.0,
    "snow_1h": 0.0,
    "clouds_all": 90,
    "holiday": null,
    "weather": [
      {
        "main": "Rain",
        "description": "light rain"
      },
      {
        "main": "Mist",
        "description": "mist"
      }
    ],
    "id": "6adf4b20c09ec4df5610bb7b"
  }
}
```

### PASS `GET /mongo/records/6adf4b20c09ec4df5610bb7b` -> 404 (expected 404)

Response:
```json
{
  "detail": "Record 6adf4b20c09ec4df5610bb7b not found"
}
```
