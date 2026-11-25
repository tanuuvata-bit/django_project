# my_website/analytics/route_planning_engine.py
import polars as pl
import json
from datetime import datetime
from django_admin.models import OrderRecord


def analyze_route_planning(identifier: str) -> dict:
    cursor = OrderRecord.objects(identifier=identifier).only("raw").as_pymongo()

    records = []
    for doc in cursor:
        item = doc.get("raw", {}).get("__json__", {})
        if not item: continue

        date_str = item.get('date')
        if not date_str: continue

        assignment = item.get('assignment_load')
        if isinstance(assignment, str):
            try:
                assignment = json.loads(assignment)
            except:
                continue
        if not isinstance(assignment, dict): continue

        for vehicle_id, trips in assignment.items():
            if not isinstance(trips, dict): continue
            for trip_id, stops in trips.items():
                if not isinstance(stops, dict): continue

                # --- Extract Warehouse Key for this Trip ---
                wh_details = stops.get('Warehouse', {})
                wh_loc = wh_details.get('location') or [None, None]
                wh_key = f"{wh_loc[0]}_{wh_loc[1]}" if wh_loc and wh_loc[0] and wh_loc[1] else "Unknown"

                for order_id, details in stops.items():
                    if not isinstance(details, dict) or order_id == 'Warehouse':
                        continue

                    loc = details.get('location') or [None, None]
                    dist_list = details.get('distance') or []
                    dist_str = str(dist_list[0]) if dist_list else None
                    times = details.get('time') or []
                    time_str = str(times[0]) if times else ""

                    records.append({
                        "date": str(date_str)[:10],
                        "vehicle_id": str(vehicle_id),
                        "trip_id": str(trip_id),
                        "order_id": str(order_id),
                        "time": time_str,
                        "warehouse_key": wh_key,  # <--- Attached to every order
                        "latitude": float(loc[0]) if loc and loc[0] else None,
                        "longitude": float(loc[1]) if loc and len(loc) > 1 and loc[1] else None,
                        "distance_str": dist_str,
                    })

    if not records:
        return {"error": "No valid route data found in JSON."}

    schema = {
        "date": pl.Utf8,
        "vehicle_id": pl.Utf8,
        "trip_id": pl.Utf8,
        "order_id": pl.Utf8,
        "time": pl.Utf8,
        "warehouse_key": pl.Utf8,
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "distance_str": pl.Utf8,
    }
    df = pl.DataFrame(records, schema=schema)

    df = df.with_columns(
        pl.col("distance_str").str.extract(r"([\d.]+)\s*km", 1).cast(pl.Float64, strict=False).alias("distance_km")
    )

    df = df.with_columns(pl.col("date").str.to_datetime(strict=False).alias("_dt"))
    df = df.filter(
        (pl.col("_dt") >= datetime(2026, 10, 9)) &
        (pl.col("_dt") <= datetime(2026, 10, 16))
    )

    phases = []

    vehicle_daily = (
        df.group_by(["date", "vehicle_id"], maintain_order=True)
        .agg([
            pl.col("order_id").n_unique().alias("orders_fulfilled"),
            pl.col("distance_km").sum().round(2).alias("total_route_distance_km"),
            pl.col("latitude").first().alias("wh_lat"),
            pl.col("longitude").first().alias("wh_lng")
        ])
        .sort("date")
    )

    vehicle_daily = vehicle_daily.with_columns(
        pl.when(pl.col("wh_lat").is_not_null() & pl.col("wh_lng").is_not_null())
        .then(pl.concat_str([pl.col("wh_lat").cast(pl.Utf8), pl.lit("_"), pl.col("wh_lng").cast(pl.Utf8)]))
        .otherwise(pl.lit("N/A")).alias("warehouse_id")
    )

    top_vehicles = (
        vehicle_daily.group_by("vehicle_id")
        .agg(pl.col("orders_fulfilled").sum().alias("orders"))
        .sort("orders", descending=True)
        .head(10)
    )
    phases.append({
        "name": "top_vehicles",
        "chart": "h_bar",
        "title": "Top Vehicles by Orders Fulfilled",
        "labels": top_vehicles["vehicle_id"].to_list(),
        "values": top_vehicles["orders"].to_list(),
        "color": "#6366f1"
    })

    top_5 = top_vehicles["vehicle_id"].head(5).to_list()
    v_dist = (
        vehicle_daily.filter(pl.col("vehicle_id").is_in(top_5))
        .group_by(["date", "vehicle_id"])
        .agg(pl.col("total_route_distance_km").sum().alias("km"))
        .sort("date")
    )
    phases.append({
        "name": "vehicle_daily_distance",
        "chart": "multi_line",
        "title": "Vehicle Daily Route Distance (Top 5)",
        "labels": v_dist["date"].unique().sort().to_list(),
        "series": [
            {
                "name": v_id,
                "values": v_dist.filter(pl.col("vehicle_id") == v_id)["km"].to_list()
            }
            for v_id in v_dist["vehicle_id"].unique().to_list()
        ]
    })

    # ==========================================
    # --- MAP: Vehicle Route Movement ---
    # ==========================================
    target_vehicle = "vehicle_301"
    target_date_map = "2026-10-09"

    map_df = df.filter(
        (pl.col("vehicle_id") == target_vehicle) &
        (pl.col("date") == target_date_map) &
        pl.col("latitude").is_not_null() &
        pl.col("longitude").is_not_null()
    ).sort(["time", "order_id"])

    if map_df.is_empty():
        v_df = df.filter((pl.col("vehicle_id") == target_vehicle) & pl.col("latitude").is_not_null())
        if not v_df.is_empty():
            first_avail_date = v_df["date"].unique().sort().to_list()[0]
            map_df = v_df.filter(pl.col("date") == first_avail_date).sort(["time", "order_id"])
            target_date_map = first_avail_date

    if not map_df.is_empty():
        phases.append({
            "name": "vehicle_route_map",
            "chart": "route_map",
            "title": f"Daily Route Map: {target_vehicle.upper()} ({target_date_map})",
            "lat": map_df["latitude"].to_list(),
            "lon": map_df["longitude"].to_list(),
            "labels": map_df["order_id"].to_list()
        })

    # ==========================================
    # NEW: CASCADING ROUTE MAP DATASET
    # ==========================================
    WAREHOUSE_MAP = {
        "17.5333611_78.4776389": "Hyderabad Hub",
        "22.9973333_72.5866389": "Ahmedabad Hub",
        "21.1773889_78.9861389": "Nagpur Hub",
        "28.5561389_77.0300556": "Delhi Hub",
        "28.4948056_77.0596389": "Gurugram Hub",
        "28.6115833_77.3745": "Noida Hub",
        "18.5444444_73.9281111": "Pune East Hub",
        "18.5319444_73.7788611": "Pune West Hub",
        "13.0213611_77.5376667": "Bengaluru North Hub",
        "12.9506389_77.7314722": "Bengaluru East Hub",
        "13.1528889_80.2064444": "Chennai Hub",
        "21.1581111_72.97": "Surat Hub"
    }

    cascading_records = []
    map_df_cascade = df.drop_nulls(subset=["latitude", "longitude"])

    for row in map_df_cascade.iter_rows(named=True):
        # Use the warehouse_key to get the correct friendly name
        wh_name = WAREHOUSE_MAP.get(row["warehouse_key"], f"Hub @ {row['warehouse_key']}")

        cascading_records.append({
            "date": row["date"],
            "warehouse": wh_name,
            "vehicle": row["vehicle_id"],
            "order_id": row["order_id"],
            "lat": row["latitude"],
            "lon": row["longitude"],
            "time": row.get("time", "")
        })

    if cascading_records:
        phases.append({
            "name": "cascading_route_map",
            "chart": "cascading_map",
            "title": "Interactive Fleet Route Explorer",
            "records": cascading_records
        })

    return {
        "identifier": identifier,
        "computed_at": datetime.utcnow().isoformat(),
        "meta": {"rows": len(records)},
        "phases": phases
    }