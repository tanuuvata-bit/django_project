# my_website/analytics/engine.py
"""
Synchronous Polars analytics engine.
Produces business-focused phases.
"""
from datetime import datetime
import polars as pl
import numpy as np

from django_admin.models import OrderRecord


# ============================================================
# Loader
# ============================================================
def _flatten_to_dataframe(identifier: str) -> pl.DataFrame:
    """
    Load OrderRecord docs for one identifier, apply same cleaning
    as the Jupyter notebook:
      - drop rows with missing order_id or creation date
      - remove fake/test addresses
      - remove future-dated orders
    """

    cursor = OrderRecord.objects(identifier=identifier).only("raw").as_pymongo()
    rows = [doc.get("raw", {}) for doc in cursor]
    if not rows:
        return pl.DataFrame()

    df = pl.DataFrame(rows, infer_schema_length=10000)

    # ---- Filter 1: Drop rows with missing required fields ----
    if "order_id" in df.columns:
        df = df.filter(
            pl.col("order_id").is_not_null() &
            (pl.col("order_id").cast(pl.Utf8).str.strip_chars() != "")
        )

    # ---- Filter 2: Remove fake/test addresses ----
    addr_col = None
    for c in df.columns:
        cl = c.lower().strip()
        if cl in ("cutomeraddress", "customer_address", "address"):
            addr_col = c
            break

    if addr_col:
        fake_pattern = "(?i)test|dummy|asdf|xyz|abc"
        df = df.filter(
            pl.col(addr_col).is_null() |
            ~pl.col(addr_col).cast(pl.Utf8, strict=False).str.contains(fake_pattern)
        )

    # ---- Filter 3: Remove future-dated orders ----
    date_col = None
    for c in df.columns:
        cl = c.lower().strip()
        if cl in ("order creation date", "order_creation_date",
                  "created_at", "creation_date", "order_date", "date"):
            date_col = c
            break

    if date_col:
        try:
            df = df.with_columns(
                pl.col(date_col).cast(pl.Utf8, strict=False)
                  .str.replace("Z", "")
                  .str.to_datetime(strict=False, time_unit="us")
                  .alias("_d")
            ).filter(
                pl.col("_d").is_null() | (pl.col("_d") <= datetime.utcnow())
            ).drop("_d")
        except Exception:
            pass

    return df

# ============================================================
# Column detection
# ============================================================
def _roles(df: pl.DataFrame) -> dict:
    cl = {c.lower().strip(): c for c in df.columns}

    def f(*names):
        for n in names:
            if n in cl:
                return cl[n]
        return None

    return {
        "order_id":        f("order_id", "orderid", "id", "order_no", "request_id"),
        "status":          f("status_name", "status", "order_status"),
        "city":            f("city", "town"),
        "state":           f("name", "state", "region", "province"),
        "pincode":         f("pincode", "pin_code", "zip", "postal_code"),
        "date":            f("order creation date", "order_creation_date",
                             "created_at", "creation_date", "order_date",
                             "date", "real_date"),
        "status_date":     f("status_date", "status date"),
        "lat":             f("latitude", "lat"),
        "lon":             f("longitude", "lon", "lng", "long"),

        "item_count":      f("item_count", "items", "qty", "quantity",
                             "num_items", "item_qty"),
        "category":        f("category", "product_category", "item_type",
                             "product_type", "product", "product_title"),
        "processing_time": f("processing_time", "dwell_time", "duration",
                             "processing_mins", "time_taken", "processing_time_mins"),
        "start_time":      f("arrival_time", "start_time", "check_in",
                             "arrived_at", "pickup_start"),
        "end_time":        f("completion_time", "end_time", "check_out",
                             "completed_at", "pickup_end"),
        "warehouse":       f("warehouse", "hub", "location", "warehouse_name"),
        "route_id":        f("route_id", "trip_id", "route", "stop_id"),
    }


# ============================================================
# Basket classification (Cancel > Completed > Pending)
# ============================================================
def _classify_baskets(df: pl.DataFrame, r: dict) -> pl.DataFrame:
    if not r["status"] or not r["order_id"]:
        return df

    df = df.with_columns(
        pl.col(r["status"]).cast(pl.Utf8, strict=False)
          .str.to_lowercase().str.strip_chars().alias("_s")
    )

    per_order = (
        df.group_by(r["order_id"])
          .agg(pl.col("_s").unique().alias("_statuses"))
          .with_columns(
              pl.when(
                  pl.col("_statuses").list.contains("cancel") |
                  pl.col("_statuses").list.contains("cancelled")
              ).then(pl.lit("Cancelled"))
              .when(
                  pl.col("_statuses").list.eval(pl.element().str.starts_with("grn")).list.any() |
                  pl.col("_statuses").list.contains("pickedup")
              ).then(pl.lit("Completed"))
              .otherwise(pl.lit("Pending"))
              .alias("_basket")
          )
          .select([r["order_id"], "_basket"])
    )

    return df.join(per_order, on=r["order_id"], how="left")


# ============================================================
# Helpers
# ============================================================
def _parse_date(df: pl.DataFrame, col: str, alias: str) -> pl.DataFrame:
    try:
        return df.with_columns(
            pl.col(col).cast(pl.Utf8, strict=False)
              .str.replace("Z", "")
              .str.to_datetime(strict=False, time_unit="us")
              .alias(alias)
        )
    except Exception:
        return df.with_columns(pl.lit(None).alias(alias))


def _season_udf(month):
    if month in (12, 1, 2):   return "Winter"
    if month in (3, 4, 5):    return "Summer"
    if month in (6, 7, 8, 9): return "Monsoon"
    return "Festive"


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ============================================================
# Main
# ============================================================
def analyze_identifier(identifier: str) -> dict:
    df = _flatten_to_dataframe(identifier)

    # Compute column roles before meta so we can count unique orders
    r_pre = _roles(df)
    unique_orders = int(df[r_pre["order_id"]].n_unique()) if (df.height and r_pre["order_id"]) else None

    meta = {
        "rows": int(df.height),
        "cols": int(df.width),
        "columns": list(df.columns) if df.width else [],
        "unique_orders": unique_orders,
    }

    if df.height == 0:
        return {
            "identifier": identifier,
            "computed_at": datetime.utcnow().isoformat(),
            "meta": meta,
            "phases": [],
        }

    r = _roles(df)
    phases = []

    # Parse dates
    if r["date"]:
        df = _parse_date(df, r["date"], "_created_dt")
    if r["status_date"]:
        df = _parse_date(df, r["status_date"], "_status_dt")

    # Classify baskets
    df = _classify_baskets(df, r)

    # ============================================================
    # 1. Basket summary (donut)
    # ============================================================
    if "_basket" in df.columns and r["order_id"]:
        order_basket = df.select([r["order_id"], "_basket"]).unique()
        t = order_basket.group_by("_basket").len().sort("len", descending=True)
        phases.append({
            "name":   "basket_summary",
            "chart":  "donut",
            "title":  "Final Basket Distribution (Cancel > Completed > Pending)",
            "labels": t["_basket"].to_list(),
            "values": t["len"].to_list(),
            "colors": ["#ef4444", "#10b981", "#94a3b8"],
        })

    # ============================================================
    # 2. Distribution of status events per order
    # ============================================================
    if r["order_id"] and r["status"]:
        events_per_order = (
            df.group_by(r["order_id"]).len().rename({"len": "_events"})
        )
        hist = (events_per_order
                .with_columns(pl.col("_events").clip(1, 15).alias("_e"))
                .group_by("_e").len().sort("_e"))
        phases.append({
            "name":   "events_per_order_hist",
            "chart":  "column",
            "title":  "Distribution of Status Events per Order",
            "labels": [str(int(x)) for x in hist["_e"].to_list()],
            "values": hist["len"].to_list(),
        })

    # ============================================================
    # 3. Top 10 status paths
    # ============================================================
    if r["order_id"] and r["status"]:
        try:
            sort_cols = [r["order_id"]]
            if "_status_dt" in df.columns:
                sort_cols = [r["order_id"], "_status_dt"]
            df_sorted = df.sort(sort_cols)

            seq = (
                df_sorted
                .group_by(r["order_id"])
                .agg(pl.col(r["status"]).cast(pl.Utf8).alias("_seq"))
                .with_columns(pl.col("_seq").list.join(" → ").alias("_path"))
                .group_by("_path").len()
                .sort("len", descending=True).head(10)
            )
            phases.append({
                "name":   "top_status_paths",
                "chart":  "h_bar",
                "title":  "Top 10 Status Paths",
                "labels": seq["_path"].to_list(),
                "values": seq["len"].to_list(),
            })
        except Exception:
            pass

    # ============================================================
    # 4. Top 10 Cities — Most Cancellations
    # ============================================================
    if r["city"] and "_basket" in df.columns and r["order_id"]:
        try:
            order_city_basket = (
                df.select([r["order_id"], r["city"], "_basket"]).unique()
            )
            cancels = (
                order_city_basket.filter(pl.col("_basket") == "Cancelled")
                  .group_by(r["city"]).len()
                  .sort("len", descending=True).head(10)
            )
            if cancels.height > 0:
                phases.append({
                    "name":   "top_cancelled_cities",
                    "chart":  "h_bar",
                    "title":  "Top 10 Cities — Most Cancellations",
                    "labels": [str(x) for x in cancels[r["city"]].to_list()],
                    "values": cancels["len"].to_list(),
                    "color":  "#ef4444",
                })
        except Exception:
            pass

    # ============================================================
    # 5. Top 10 Cities — Most Completed Orders
    # ============================================================
    if r["city"] and "_basket" in df.columns and r["order_id"]:
        try:
            order_city_basket = (
                df.select([r["order_id"], r["city"], "_basket"]).unique()
            )
            completes = (
                order_city_basket.filter(pl.col("_basket") == "Completed")
                  .group_by(r["city"]).len()
                  .sort("len", descending=True).head(10)
            )
            if completes.height > 0:
                phases.append({
                    "name":   "top_completed_cities",
                    "chart":  "h_bar",
                    "title":  "Top 10 Cities — Most Completed Orders",
                    "labels": [str(x) for x in completes[r["city"]].to_list()],
                    "values": completes["len"].to_list(),
                    "color":  "#10b981",
                })
        except Exception:
            pass

    # ============================================================
    # 6. Order Count by Season
    # ============================================================
    if "_created_dt" in df.columns and r.get("status") is not None and df["_created_dt"].null_count() < df.height:
        try:
            if r["order_id"]:
                order_lvl = df.select([r["order_id"], "_created_dt"]).unique()
            else:
                order_lvl = df

            order_lvl = (order_lvl
                .filter(pl.col("_created_dt").is_not_null())
                .with_columns(pl.col("_created_dt").dt.month().alias("_m"))
                .with_columns(
                    pl.col("_m").map_elements(_season_udf, return_dtype=pl.Utf8)
                      .alias("_season")
                )
            )

            season_counts = order_lvl.group_by("_season").len().sort("len", descending=True)
            phases.append({
                "name":   "season_order_counts",
                "chart":  "donut",
                "title":  "Order Count by Season",
                "labels": season_counts["_season"].to_list(),
                "values": season_counts["len"].to_list(),
                "colors": ["#60a5fa", "#fbbf24", "#22d3ee", "#f472b6"],
            })

            # ============================================================
            # 7. Cancel vs Completion Rate by Season (grouped bar)
            # ============================================================
            if "_basket" in df.columns and r["order_id"]:
                per_order_basket = df.select([r["order_id"], "_basket"]).unique()
                merged = order_lvl.join(per_order_basket, on=r["order_id"], how="left")

                season_basket = merged.group_by(["_season", "_basket"]).len()
                season_total = merged.group_by("_season").len().rename({"len": "_total"})
                season_basket = (season_basket
                    .join(season_total, on="_season", how="left")
                    .with_columns((100 * pl.col("len") / pl.col("_total")).alias("_pct"))
                )

                seasons = sorted(season_basket["_season"].unique().to_list())
                cancel_pct, complete_pct = [], []
                for s in seasons:
                    row = season_basket.filter(pl.col("_season") == s)
                    cval = row.filter(pl.col("_basket") == "Cancelled")["_pct"].sum() if row.height else 0
                    kval = row.filter(pl.col("_basket") == "Completed")["_pct"].sum() if row.height else 0
                    cancel_pct.append(round(float(cval), 2))
                    complete_pct.append(round(float(kval), 2))

                phases.append({
                    "name":   "season_cancel_vs_complete",
                    "chart":  "grouped_bar",
                    "title":  "Cancel vs Completion Rate by Season (%)",
                    "labels": seasons,
                    "series": [
                        {"name": "Cancel Rate %",     "values": cancel_pct,   "color": "#ef4444"},
                        {"name": "Completion Rate %", "values": complete_pct, "color": "#10b981"},
                    ],
                })
        except Exception:
            pass

    # ============================================================
    # 8. Top 10 Cities by Total Orders
    # ============================================================
    if r["city"]:
        t = df.group_by(r["city"]).len().sort("len", descending=True).head(10)
        phases.append({
            "name":   "top_cities",
            "chart":  "h_bar",
            "title":  "Top 10 Cities by Total Orders",
            "labels": [str(x) for x in t[r["city"]].to_list()],
            "values": t["len"].to_list(),
            "color":  "#6366f1",
        })

    # ============================================================
    # 9. Peak Order Hours (area)
    # ============================================================
    if "_created_dt" in df.columns and r.get("status") is not None and df["_created_dt"].null_count() < df.height:
        h = (df.filter(pl.col("_created_dt").is_not_null())
               .with_columns(pl.col("_created_dt").dt.hour().alias("_h"))
               .group_by("_h").len().sort("_h"))
        phases.append({
            "name":   "peak_hours",
            "chart":  "area",
            "title":  "Peak Order Hours",
            "labels": [f"{int(x):02d}:00" for x in h["_h"].to_list()],
            "values": h["len"].to_list(),
        })

    # ============================================================
    # 10. Monthly Order Counts (line)
    # ============================================================
    if "_created_dt" in df.columns and r.get("status") is not None and df["_created_dt"].null_count() < df.height:
        m = (df.filter(pl.col("_created_dt").is_not_null())
               .with_columns(pl.col("_created_dt").dt.month().alias("_m"))
               .group_by("_m").len().sort("_m"))
        phases.append({
            "name":   "monthly_counts",
            "chart":  "line",
            "title":  "Monthly Order Counts",
            "labels": [MONTH_NAMES[int(x)-1] for x in m["_m"].to_list()],
            "values": m["len"].to_list(),
        })

    # ============================================================
    # 11. Top 10 Cities — Cancellation Rate (%) — only ≥100 orders
    # ============================================================
    if r["city"] and "_basket" in df.columns and r["order_id"]:
        try:
            order_city_basket = (
                df.select([r["order_id"], r["city"], "_basket"]).unique()
            )
            by_city = (
                order_city_basket.group_by(r["city"]).agg([
                    pl.len().alias("_total"),
                    (pl.col("_basket") == "Cancelled").sum().alias("_cancels"),
                ])
                .with_columns((100 * pl.col("_cancels") / pl.col("_total")).alias("_rate"))
                .filter(pl.col("_total") >= 100)             # ← NEW: threshold ≥ 100
                .sort("_rate", descending=True)
                .head(10)
            )
            if by_city.height > 0:
                phases.append({
                    "name":   "cancel_rate_by_city",
                    "chart":  "h_bar",
                    "title":  "Top 10 Cities — Cancellation Rate (%) · ≥100 orders",
                    "labels": [str(x) for x in by_city[r["city"]].to_list()],
                    "values": [round(float(x), 2) for x in by_city["_rate"].to_list()],
                    "color":  "#ef4444",
                    "suffix": "%",
                })
        except Exception:
            pass

    # ============================================================
    # 12. NEW — Monthly Impact (bar): total orders per month (order-level)
    # ============================================================
    if "_created_dt" in df.columns and r.get("status") is not None and df["_created_dt"].null_count() < df.height:
        try:
            if r["order_id"]:
                order_month = df.select([r["order_id"], "_created_dt"]).unique()
            else:
                order_month = df

            mm = (order_month
                  .filter(pl.col("_created_dt").is_not_null())
                  .with_columns(pl.col("_created_dt").dt.month().alias("_m"))
                  .group_by("_m").len().sort("_m"))

            phases.append({
                "name":   "monthly_impact",
                "chart":  "column",
                "title":  "Monthly Impact — Total Orders per Month",
                "labels": [MONTH_NAMES[int(x)-1] for x in mm["_m"].to_list()],
                "values": mm["len"].to_list(),
                "color":  "#6366f1",
            })
        except Exception:
            pass

        # ============================================================
        # 16. Fastest Growing Cities (rolling 12 months, min-volume guard)
        # ============================================================
        if (
                r["city"]
                and r["order_id"]
                and "_created_dt" in df.columns
                and df["_created_dt"].null_count() < df.height
        ):
            try:
                # ---- Step 1: order-level view (dedupe first) ----
                order_lvl = df.select([r["order_id"], r["city"], "_created_dt"]).unique()
                order_lvl = order_lvl.filter(pl.col("_created_dt").is_not_null())

                if order_lvl.height > 0:
                    # ---- Step 2: bucket into year-month ----
                    order_lvl = order_lvl.with_columns([
                        pl.col("_created_dt").dt.year().alias("_y"),
                        pl.col("_created_dt").dt.month().alias("_m"),
                    ])

                    # ---- Step 3: restrict to last 12 months ----
                    max_date = order_lvl["_created_dt"].max()
                    min_date = max_date - pl.duration(days=365)
                    recent = order_lvl.filter(pl.col("_created_dt") >= min_date)

                    # ---- Step 4: monthly counts per city ----
                    monthly = (
                        recent.group_by([r["city"], "_y", "_m"])
                        .len()
                        .sort([r["city"], "_y", "_m"])
                    )

                    # ---- Step 5: per-city summary ----
                    city_stats = monthly.group_by(r["city"]).agg([
                        pl.len().alias("_n_months"),  # distinct months present
                        pl.col("len").sum().alias("_total"),  # total orders in 12m
                        pl.col("len").first().alias("_first_val"),  # first month count
                        pl.col("len").last().alias("_last_val"),  # last month count
                        pl.col("len").mean().alias("_mean"),  # mean monthly
                        pl.col("len").slice(-3).mean().alias("_last_q_avg"),  # last 3 months avg
                        pl.col("len").slice(0, 3).mean().alias("_first_q_avg"),  # first 3 months avg
                    ])

                    # ---- Step 6: apply guards ----
                    #   - at least 500 total orders in 12m
                    #   - at least 6 distinct months of activity
                    city_stats = city_stats.filter(
                        (pl.col("_total") >= 500) & (pl.col("_n_months") >= 6)
                    )

                    # ---- Step 7: compute CMGR ----
                    # Handle zero first/last gracefully
                    city_stats = city_stats.with_columns([
                        pl.when(
                            (pl.col("_first_val") > 0) & (pl.col("_last_val") > 0)
                        ).then(
                            (pl.col("_last_val") / pl.col("_first_val"))
                            .pow(1.0 / (pl.col("_n_months") - 1))
                            - 1.0
                        ).otherwise(pl.lit(None)).alias("_cmgr"),

                        (pl.col("_last_q_avg") - pl.col("_first_q_avg")).alias("_abs_growth"),

                        ((pl.col("_last_q_avg") - pl.col("_first_q_avg"))
                         / pl.col("_mean").clip(1)).alias("_rel_growth"),
                    ])

                    # ---- Step 8: composite score ----
                    city_stats = city_stats.with_columns(
                        (0.6 * pl.col("_cmgr").fill_null(0) +
                         0.4 * pl.col("_rel_growth").fill_null(0)).alias("_growth_score")
                    )

                    # ---- Step 9: top 10 ----
                    top_growers = (
                        city_stats
                        .filter(pl.col("_growth_score").is_not_null())
                        .sort("_growth_score", descending=True)
                        .head(10)
                    )

                    if top_growers.height > 0:
                        phases.append({
                            "name": "fastest_growing_cities",
                            "chart": "h_bar",
                            "title": "Top 10 Fastest Growing Cities (rolling 12 months, ≥500 orders, ≥6 months)",
                            "labels": [
                                f"{c}  ({int(v):,} orders)"
                                for c, v in zip(
                                    top_growers[r["city"]].to_list(),
                                    top_growers["_total"].to_list(),
                                )
                            ],
                            "values": [
                                round(float(x) * 100, 2)  # % per month
                                for x in top_growers["_growth_score"].to_list()
                            ],
                            "color": "#10b981",
                            "suffix": "%",
                        })
            except Exception:
                pass

            # ============================================================
            # 17. Monthly Impact — Top 5 Fastest Growing Cities (Chart A)
            #     + Next 5 Fastest Growing Cities (Chart B)
            # ============================================================
            if (
                    r["city"] and r["order_id"]
                    and "_created_dt" in df.columns
                    and df["_created_dt"].null_count() < df.height
            ):
                try:
                    # ---- Recompute the top 10 growing cities (same logic) ----
                    order_lvl = df.select([r["order_id"], r["city"], "_created_dt"]).unique()
                    order_lvl = order_lvl.filter(pl.col("_created_dt").is_not_null())

                    if order_lvl.height > 0:
                        order_lvl = order_lvl.with_columns([
                            pl.col("_created_dt").dt.year().alias("_y"),
                            pl.col("_created_dt").dt.month().alias("_m"),
                        ])

                        # Restrict to last 12 months
                        max_date = order_lvl["_created_dt"].max()
                        min_date = max_date - pl.duration(days=365)
                        recent = order_lvl.filter(pl.col("_created_dt") >= min_date)

                        # Monthly counts per city
                        monthly = (
                            recent.group_by([r["city"], "_y", "_m"])
                            .len()
                            .sort([r["city"], "_y", "_m"])
                        )

                        # Rank cities by growth (same formula as Phase 16)
                        city_stats = monthly.group_by(r["city"]).agg([
                            pl.len().alias("_n_months"),
                            pl.col("len").sum().alias("_total"),
                            pl.col("len").first().alias("_first_val"),
                            pl.col("len").last().alias("_last_val"),
                            pl.col("len").mean().alias("_mean"),
                            pl.col("len").slice(-3).mean().alias("_last_q_avg"),
                            pl.col("len").slice(0, 3).mean().alias("_first_q_avg"),
                        ]).filter(
                            (pl.col("_total") >= 500) & (pl.col("_n_months") >= 6)
                        ).with_columns([
                            pl.when(
                                (pl.col("_first_val") > 0) & (pl.col("_last_val") > 0)
                            ).then(
                                (pl.col("_last_val") / pl.col("_first_val"))
                                .pow(1.0 / (pl.col("_n_months") - 1)) - 1.0
                            ).otherwise(pl.lit(None)).alias("_cmgr"),
                            ((pl.col("_last_q_avg") - pl.col("_first_q_avg"))
                             / pl.col("_mean").clip(1)).alias("_rel_growth"),
                        ]).with_columns(
                            (0.6 * pl.col("_cmgr").fill_null(0) +
                             0.4 * pl.col("_rel_growth").fill_null(0)).alias("_growth_score")
                        ).filter(
                            pl.col("_growth_score").is_not_null()
                        ).sort("_growth_score", descending=True).head(10)

                        top10_cities = top_growers_cities = city_stats[r["city"]].to_list()

                        # Build chronological month labels for the last 12 months
                        month_grid = (
                            recent.select(["_y", "_m"]).unique().sort(["_y", "_m"])
                        )
                        month_labels = [
                            f"{int(m):02d}/{str(int(y))[2:]}"
                            for y, m in zip(month_grid["_y"].to_list(),
                                            month_grid["_m"].to_list())
                        ]

                        def _series_for(city):
                            """Return orders-per-month list for a city, aligned to month_grid."""
                            city_monthly = monthly.filter(pl.col(r["city"]) == city)
                            lookup = {
                                (int(row["_y"]), int(row["_m"])): int(row["len"])
                                for row in city_monthly.iter_rows(named=True)
                            }
                            return [
                                lookup.get((int(y), int(m)), 0)
                                for y, m in zip(month_grid["_y"].to_list(),
                                                month_grid["_m"].to_list())
                            ]

                        # Split into two groups of 5
                        first_five = top10_cities[:5]
                        second_five = top10_cities[5:10]

                        def _build_group(group, chart_name, title_suffix):
                            series = []
                            for city in group:
                                series.append({
                                    "name": city,
                                    "values": _series_for(city),
                                })
                            if series:
                                phases.append({
                                    "name": chart_name,
                                    "chart": "multi_line",
                                    "title": f"Monthly Orders — Fastest Growing Cities {title_suffix}",
                                    "labels": month_labels,
                                    "series": series,
                                })

                        _build_group(first_five, "growth_monthly_chart_a", "(Group A)")
                        _build_group(second_five, "growth_monthly_chart_b", "(Group B)")

                except Exception:
                    pass

    # ============================================================
    # 13. NEW — Orders between 6 AM and 6 PM (donut)
    # ============================================================
    if "_created_dt" in df.columns and r.get("status") is not None and df["_created_dt"].null_count() < df.height:
        try:
            if r["order_id"]:
                order_hour = df.select([r["order_id"], "_created_dt"]).unique()
            else:
                order_hour = df

            oh = order_hour.filter(pl.col("_created_dt").is_not_null()).with_columns(
                pl.col("_created_dt").dt.hour().alias("_h")
            )

            daytime = oh.filter((pl.col("_h") >= 6) & (pl.col("_h") < 18)).height
            nighttime = oh.height - daytime

            phases.append({
                "name":   "daytime_vs_night",
                "chart":  "donut",
                "title":  "Orders 6 AM – 6 PM vs Outside",
                "labels": ["6 AM – 6 PM", "Other hours"],
                "values": [int(daytime), int(nighttime)],
                "colors": ["#22d3ee", "#94a3b8"],
            })
        except Exception:
            pass

    # ============================================================
    # 14. Geo points (map) — optional
    # ============================================================
    if r["lat"] and r["lon"]:
        try:
            g = (df.select([
                    pl.col(r["lat"]).cast(pl.Float64, strict=False).alias("lat"),
                    pl.col(r["lon"]).cast(pl.Float64, strict=False).alias("lon"),
                 ])
                 .drop_nulls()
                 .filter((pl.col("lat").abs() <= 90) & (pl.col("lon").abs() <= 180)))
            if g.height > 5000:
                g = g.sample(5000, seed=42)
            if g.height > 0:
                phases.append({
                    "name":   "geo_points",
                    "chart":  "map",
                    "title":  "Geographic Distribution",
                    "lat":    g["lat"].to_list(),
                    "lon":    g["lon"].to_list(),
                })
        except Exception:
            pass

    # ============================================================
    # Fallback
    # ============================================================
    if not phases:
        phases.append({
            "name":   "total_rows",
            "chart":  "column",
            "title":  "Total Rows",
            "labels": ["Total"],
            "values": [df.height],
        })

    return {
        "identifier": identifier,
        "computed_at": datetime.utcnow().isoformat(),
        "meta": meta,
        "phases": phases,
    }