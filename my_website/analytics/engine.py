# my_website/analytics/engine.py
"""
Synchronous Polars analytics engine.
Reads OrderRecord documents from MongoDB → returns JSON summary.
No Celery, no GridFS, no async.
"""
from datetime import datetime
import polars as pl
import numpy as np

from django_admin.models import OrderRecord


def _flatten_to_dataframe(identifier: str) -> pl.DataFrame:
    """
    Pull OrderRecord docs for one identifier and flatten `raw` into columns.
    """
    cursor = OrderRecord.objects(identifier=identifier).only("raw").as_pymongo()
    rows = [doc.get("raw", {}) for doc in cursor]

    if not rows:
        return pl.DataFrame()

    # Polars infers schema from list of dicts
    df = pl.DataFrame(rows, infer_schema_length=10000)
    return df


def _roles(df: pl.DataFrame) -> dict:
    cl = {c.lower().strip(): c for c in df.columns}

    def f(*names):
        for n in names:
            if n in cl:
                return cl[n]
        return None

    return {
        "status":   f("status_name", "status"),
        "city":     f("city"),
        "state":    f("name", "state"),
        "date":     f("order creation date", "order_creation_date", "created_at"),
        "lat":      f("latitude", "lat"),
        "lon":      f("longitude", "lon", "lng"),
    }


def analyze_identifier(identifier: str) -> dict:
    """
    Main entry. Reads docs for `identifier`, returns JSON summary.
    """
    df = _flatten_to_dataframe(identifier)

    out = {
        "identifier": identifier,
        "computed_at": datetime.utcnow().isoformat(),
        "meta": {"rows": df.height, "cols": df.width, "columns": df.columns},
        "phases": {},
    }

    if df.height == 0:
        return out

    # Coerce date columns to real datetimes if they're strings
    r = _roles(df)

    if r["date"]:
        try:
            df = df.with_columns(
                pl.col(r["date"]).cast(pl.Utf8, strict=False)
                  .str.replace("Z", "")
                  .str.to_datetime(strict=False, time_unit="us")
                  .alias("_dt")
            )
        except Exception:
            df = df.with_columns(pl.lit(None).alias("_dt"))
    else:
        df = df.with_columns(pl.lit(None).alias("_dt"))

    # Re-resolve roles after transformations
    r = _roles(df)
    if "_dt" in df.columns and df["_dt"].null_count() < df.height:
        r["date"] = "_dt"

    # ---- 1. Status distribution ----
    if r["status"]:
        t = df.group_by(r["status"]).len().sort("len", descending=True).head(15)
        out["phases"]["status_distribution"] = {
            "labels": [str(x) for x in t[r["status"]].to_list()],
            "values": t["len"].to_list(),
        }

    # ---- 2. Top cities ----
    if r["city"]:
        t = df.group_by(r["city"]).len().sort("len", descending=True).head(10)
        out["phases"]["top_cities"] = {
            "labels": [str(x) for x in t[r["city"]].to_list()],
            "values": t["len"].to_list(),
        }

    # ---- 3. Top states ----
    if r["state"]:
        t = df.group_by(r["state"]).len().sort("len", descending=True).head(10)
        out["phases"]["top_states"] = {
            "labels": [str(x) for x in t[r["state"]].to_list()],
            "values": t["len"].to_list(),
        }

    # ---- Date-driven phases ----
    if r["date"] == "_dt":
        d = df.with_columns([
            pl.col("_dt").dt.month().alias("_m"),
            pl.col("_dt").dt.hour().alias("_h"),
        ]).filter(pl.col("_m").is_not_null())

        monthly = d.group_by("_m").len().sort("_m")
        out["phases"]["monthly_counts"] = {
            "labels": [f"M{int(m):02d}" for m in monthly["_m"].to_list()],
            "values": monthly["len"].to_list(),
        }

        hourly = d.group_by("_h").len().sort("_h")
        out["phases"]["peak_hours"] = {
            "labels": [f"{int(h):02d}:00" for h in hourly["_h"].to_list()],
            "values": hourly["len"].to_list(),
        }

        if r["status"]:
            cancels = (
                d.filter(
                    pl.col(r["status"]).cast(pl.Utf8, strict=False)
                      .str.to_lowercase()
                      .is_in(["cancel", "cancelled"])
                )
                .group_by("_m").len().sort("_m")
            )
            out["phases"]["cancellation_by_month"] = {
                "labels": [f"M{int(m):02d}" for m in cancels["_m"].to_list()],
                "values": cancels["len"].to_list(),
            }

        hvals = d["_h"].drop_nulls().to_numpy()
        if len(hvals) > 0:
            hist, edges = np.histogram(hvals, bins=24, range=(0, 24))
            out["phases"]["processing_time_hist"] = {
                "labels": [f"{int(edges[i]):02d}–{int(edges[i+1]):02d}" for i in range(len(hist))],
                "values": hist.tolist(),
            }

    # ---- Geo points ----
    if r["lat"] and r["lon"]:
        try:
            g = (
                df.select([
                    pl.col(r["lat"]).cast(pl.Float64, strict=False).alias("lat"),
                    pl.col(r["lon"]).cast(pl.Float64, strict=False).alias("lon"),
                ])
                .drop_nulls()
                .filter((pl.col("lat").abs() <= 90) & (pl.col("lon").abs() <= 180))
            )
            if g.height > 5000:
                g = g.sample(5000, seed=42)
            if g.height > 0:
                out["phases"]["geo_points"] = {
                    "lat": g["lat"].to_list(),
                    "lon": g["lon"].to_list(),
                }
        except Exception:
            pass

    return out