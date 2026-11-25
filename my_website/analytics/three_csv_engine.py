# my_website/analytics/three_csv_engine.py
import polars as pl
from datetime import datetime
from django_admin.models import OrderRecord


def analyze_three_csv(identifier: str) -> dict:
    cursor = OrderRecord.objects(identifier=identifier).only("raw").as_pymongo()

    time_records, date_records, product_records = [], [], []

    for doc in cursor:
        raw = doc.get("raw", {})
        if not raw: continue

        if "product_title" in raw:
            product_records.append(raw)
        elif "time_start_raw" in raw:
            time_records.append(raw)
        elif "real_date" in raw:
            date_records.append(raw)

    if not time_records or not date_records or not product_records:
        return {
            "error": f"Found {len(time_records)} Time, {len(date_records)} Date, and {len(product_records)} Product rows. Please ensure all 3 files are uploaded under '{identifier}'."}

    df_time = pl.DataFrame(time_records)

    # 1. Clean dates
    df_date_clean = pl.DataFrame(date_records).select(["order_id", "vehicle_id", "real_date"]).unique()

    # 2. THE FIX: Deduplicate EXACT items, THEN group them so we don't lose multi-items
    df_product_unique = (
        pl.DataFrame(product_records)
        .select(["order_id", "vehicle_id", "product_title"])
        .drop_nulls(subset=["product_title"])
        .with_columns(pl.col("product_title").cast(pl.Utf8).str.strip_chars())
        .unique()  # Removes exact duplicates (e.g., 2 identical ACs become 1)
    )

    df_product_grouped = (
        df_product_unique
        .group_by(["order_id", "vehicle_id"])
        .agg(pl.col("product_title").str.concat(", ").alias("product_title"))
    )

    # 3. Merge everything together
    merged = df_time.join(df_date_clean, on=["order_id", "vehicle_id"], how="inner")
    merged = merged.join(df_product_grouped, on=["order_id", "vehicle_id"], how="left")

    # 4. Process dates
    merged = merged.with_columns([
        pl.concat_str([pl.col("real_date").cast(pl.Utf8), pl.lit(" "), pl.col("time_start_raw").cast(pl.Utf8)]).alias(
            "start_str"),
        pl.concat_str([pl.col("real_date").cast(pl.Utf8), pl.lit(" "), pl.col("time_end_raw").cast(pl.Utf8)]).alias(
            "end_str")
    ])

    merged = merged.with_columns([
        pl.coalesce([
            pl.col("start_str").str.to_datetime("%Y-%m-%d %I:%M:%S %p", strict=False),
            pl.col("start_str").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
        ]).alias("start_dt"),

        pl.coalesce([
            pl.col("end_str").str.to_datetime("%Y-%m-%d %I:%M:%S %p", strict=False),
            pl.col("end_str").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
        ]).alias("end_dt"),

        pl.col("processing_time_mins").cast(pl.Float64, strict=False)
    ])

    merged = merged.drop_nulls(subset=["start_dt", "end_dt"])

    # Filter for the requested date range
    merged = merged.filter(
        (pl.col("start_dt") >= datetime(2026, 10, 9)) &
        (pl.col("start_dt") <= datetime(2026, 10, 16, 23, 59, 59))
    )

    # 5. Drop the "ghost" duplicates (reassignments) but keep the concatenated items
    merged = merged.sort("start_dt").unique(subset=["order_id", "real_date"], keep="first")

    phases = []
    target_date = "2026-10-09"
    day_df = merged.filter(pl.col("real_date") == target_date)

    if not day_df.is_empty():
        # ==========================================
        # PHASE 1: Total Stops per Vehicle (Horizontal Bar)
        # ==========================================
        stops_per_vehicle = (
            day_df.group_by("vehicle_id")
            .agg(pl.col("order_id").n_unique().alias("total_stops"))
            .sort("total_stops", descending=True)
            .head(30)
        )

        phases.append({
            "name": "orders_per_vehicle",
            "chart": "h_bar",
            "title": f"Top 30 Vehicles by Total Stops ({target_date})",
            "labels": stops_per_vehicle["vehicle_id"].to_list(),
            "values": stops_per_vehicle["total_stops"].to_list(),
            "color": "#6366f1"
        })

        # ==========================================
        # PHASE 2: Daily Route Agenda (Timeline)
        # ==========================================
        target_vehicle = "vehicle_301"
        v301_df = day_df.filter(pl.col("vehicle_id") == target_vehicle).sort("start_dt")

        if not v301_df.is_empty():
            timeline_rows = []
            for r in v301_df.iter_rows(named=True):
                dur = r["processing_time_mins"]
                if dur < 20:
                    color = "#10b981"
                elif dur < 45:
                    color = "#f59e0b"
                else:
                    color = "#ef4444"

                timeline_rows.append({
                    "time_start": r["time_start_raw"],
                    "time_end": r["time_end_raw"],
                    "vehicle": r["vehicle_id"],
                    "order_id": r["order_id"],
                    "product_title": r["product_title"],  # Now contains ALL distinct items!
                    "duration": round(dur, 2),
                    "color": color
                })

            last_row = v301_df.tail(1).to_dicts()[0]
            timeline_rows.append({
                "time_start": last_row["time_end_raw"],
                "time_end": "",
                "vehicle": "END",
                "order_id": "END OF ROUTE",
                "product_title": "",
                "duration": 0,
                "color": "#1e293b"
            })

            phases.append({
                "name": "daily_route_agenda",
                "chart": "timeline_3csv",
                "title": f"Daily Route Agenda: {target_vehicle.upper()} ({target_date})",
                "rows": timeline_rows
            })

    return {
        "identifier": identifier,
        "computed_at": datetime.utcnow().isoformat(),
        "meta": {"rows": len(merged)},
        "phases": phases
    }

