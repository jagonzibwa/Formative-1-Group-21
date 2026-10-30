"""Draw the MySQL ERD to database/erd.png (Task 2).

Usage:  python -m database.draw_erd

The tables and columns below mirror database/mysql/schema.sql.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from src import config

# (table, x, y_top, [(column, type, key)])   key: PK, FK, UQ or ""
TABLES = [
    ("holidays", 0.0, 7.2, [
        ("holiday_id", "INT", "PK"),
        ("holiday_date", "DATE", "UQ"),
        ("holiday_name", "VARCHAR(50)", ""),
    ]),
    ("traffic_readings", 5.2, 8.0, [
        ("reading_id", "INT", "PK"),
        ("date_time", "DATETIME", "UQ"),
        ("traffic_volume", "INT", ""),
        ("holiday_id", "INT NULL", "FK"),
    ]),
    ("weather_observations", 10.4, 8.0, [
        ("observation_id", "INT", "PK"),
        ("reading_id", "INT", "FK"),
        ("condition_id", "SMALLINT", "FK"),
        ("temp", "DECIMAL(6,2)", ""),
        ("rain_1h", "DECIMAL(7,2)", ""),
        ("snow_1h", "DECIMAL(5,2)", ""),
        ("clouds_all", "TINYINT", ""),
    ]),
    ("weather_conditions", 10.4, 3.2, [
        ("condition_id", "SMALLINT", "PK"),
        ("main", "VARCHAR(20)", "UQ"),
        ("description", "VARCHAR(50)", "UQ"),
    ]),
]

# (from table, from col, to table, to col, label at "one" end, label at "many" end)
RELATIONS = [
    ("holidays", "holiday_id", "traffic_readings", "holiday_id", "1", "0..N"),
    ("traffic_readings", "reading_id", "weather_observations", "reading_id", "1", "1..N"),
    ("weather_conditions", "condition_id", "weather_observations", "condition_id", "1", "0..N"),
]

W, ROW, HEAD = 4.2, 0.45, 0.6
HEADER_COLOR, KEY_COLOR, LINE_COLOR = "#1f3a5f", "#b5452a", "#555555"


def _row_y(table, column):
    name, x, top, cols = next(t for t in TABLES if t[0] == table)
    i = [c[0] for c in cols].index(column)
    return top - HEAD - ROW * (i + 0.5)


def draw(path):
    fig, ax = plt.subplots(figsize=(15, 8))
    for name, x, top, cols in TABLES:
        height = HEAD + ROW * len(cols)
        ax.add_patch(FancyBboxPatch((x, top - height), W, height, boxstyle="round,pad=0.02",
                                    fc="white", ec=HEADER_COLOR, lw=1.5))
        ax.add_patch(FancyBboxPatch((x, top - HEAD), W, HEAD, boxstyle="round,pad=0.02",
                                    fc=HEADER_COLOR, ec=HEADER_COLOR))
        ax.text(x + W / 2, top - HEAD / 2, name, ha="center", va="center",
                color="white", fontsize=12, weight="bold")
        for i, (col, typ, key) in enumerate(cols):
            y = top - HEAD - ROW * (i + 0.5)
            ax.text(x + 0.15, y, key, va="center", fontsize=9, weight="bold", color=KEY_COLOR)
            ax.text(x + 0.65, y, col, va="center", fontsize=10,
                    weight="bold" if key == "PK" else "normal")
            ax.text(x + W - 0.15, y, typ, va="center", ha="right", fontsize=9, color="#666666")

    pos = {t[0]: (t[1], t[2]) for t in TABLES}
    for src, scol, dst, dcol, one, many in RELATIONS:
        y1, y2 = _row_y(src, scol), _row_y(dst, dcol)
        x_src, x_dst = pos[src][0], pos[dst][0]
        if x_src < x_dst:            # left-to-right link
            x1, x2 = x_src + W, x_dst
            xm = (x1 + x2) / 2
            ax.plot([x1, xm, xm, x2], [y1, y1, y2, y2], color=LINE_COLOR, lw=1.4)
            ax.text(x1 + 0.1, y1 + 0.12, one, fontsize=10, weight="bold")
            ax.text(x2 - 0.1, y2 + 0.12, many, fontsize=10, weight="bold", ha="right")
        else:                        # stacked tables: link along the right side
            x1 = x2 = x_src + W
            xm = x1 + 0.5
            ax.plot([x1, xm, xm, x2], [y1, y1, y2, y2], color=LINE_COLOR, lw=1.4)
            ax.text(x1 + 0.1, y1 + 0.12, one, fontsize=10, weight="bold")
            ax.text(x2 + 0.1, y2 + 0.12, many, fontsize=10, weight="bold")

    ax.text(0, 0.6, "PK primary key   FK foreign key   UQ unique   ·   "
            "one traffic reading per hour; one or more weather observations per reading",
            fontsize=9, color="#666666")
    ax.set_xlim(-0.3, 15.6)
    ax.set_ylim(0.3, 8.4)
    ax.axis("off")
    ax.set_title("metro_traffic: MySQL entity-relationship diagram", fontsize=14,
                 weight="bold", loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"Saved {path.relative_to(config.ROOT_DIR)}")


if __name__ == "__main__":
    draw(config.ROOT_DIR / "database" / "erd.png")
