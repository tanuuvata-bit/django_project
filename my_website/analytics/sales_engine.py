# my_website/analytics/sales_engine.py
import pandas as pd
import numpy as np
from datetime import datetime
from django_admin.models import OrderRecord


def analyze_sales(identifier: str) -> dict:
    # 1. Load Data
    cursor = OrderRecord.objects(identifier=identifier).only("raw").as_pymongo()
    rows = [doc.get("raw", {}) for doc in cursor]
    if not rows:
        return {"error": f"No data found for {identifier}"}

    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip()

    # Convert types
    df['processing_time_mins'] = pd.to_numeric(df['processing_time_mins'], errors='coerce')
    df['item_count'] = pd.to_numeric(df['item_count'], errors='coerce')
    df['product_title'] = df['product_title'].fillna('Unknown')
    df['real_date'] = pd.to_datetime(df['real_date'], errors='coerce')
    df = df.dropna(subset=['real_date'])

    # --- PHASE 1: Order Level Scatter ---
    df_orders = df.drop_duplicates(subset=['order_id']).copy()
    df_orders = df_orders[(df_orders['processing_time_mins'] > 0) & (df_orders['item_count'] > 0)]
    df_orders['time_per_item'] = df_orders['processing_time_mins'] / df_orders['item_count']

    scatter_data = df_orders[['item_count', 'processing_time_mins']].dropna()
    scatter_points = [{"x": float(r['item_count']), "y": float(r['processing_time_mins'])} for _, r in
                      scatter_data.iterrows()]
    # TO LIMIT TO 1000 ROWS:
    # Find this line:
    scatter_data = df_orders[['item_count', 'processing_time_mins']].dropna()

    # Replace everything below it down to trend_data with this:
    scatter_sample = scatter_data.sample(min(1000, len(scatter_data)), random_state=42)
    scatter_points = [{"x": float(r['item_count']), "y": float(r['processing_time_mins'])} for _, r in
                      scatter_sample.iterrows()]

    # Trendline (uses the FULL scatter_data so the math is accurate)
    try:
        z = np.polyfit(scatter_data['item_count'], scatter_data['processing_time_mins'], 1)
        p = np.poly1d(z)
        x_min, x_max = scatter_data['item_count'].min(), scatter_data['item_count'].max()
        trend_data = [{"x": float(x_min), "y": float(p(x_min))}, {"x": float(x_max), "y": float(p(x_max))}]
    except Exception:
        trend_data = []

    # Trendline
    try:
        z = np.polyfit(scatter_data['item_count'], scatter_data['processing_time_mins'], 1)
        p = np.poly1d(z)
        x_min, x_max = scatter_data['item_count'].min(), scatter_data['item_count'].max()
        trend_data = [{"x": float(x_min), "y": float(p(x_min))}, {"x": float(x_max), "y": float(p(x_max))}]
    except Exception:
        trend_data = []

    # --- PHASE 2: Summary by Item Range ---
    bins = [0, 2, 5, 10, 20, 100]
    labels = ['1-2 items', '3-5 items', '6-10 items', '11-20 items', '20+ items']
    df_orders['item_range'] = pd.cut(df_orders['item_count'], bins=bins, labels=labels)

    summary = []
    for label in labels:
        sub = df_orders[df_orders['item_range'] == label]
        if len(sub) > 0:
            summary.append({
                "range": label,
                "orders": int(len(sub)),
                "avg": round(float(sub['processing_time_mins'].mean()), 2),
                "min": round(float(sub['processing_time_mins'].min()), 2),
                "max": round(float(sub['processing_time_mins'].max()), 2),
                "p95": round(float(np.percentile(sub['processing_time_mins'], 95)), 2),
                "avg_per_item": round(float(sub['time_per_item'].mean()), 2)
            })

    # --- PHASE 3: Z-Score Outliers ---
    stats = df_orders.groupby('item_count')['processing_time_mins'].agg(['mean', 'std']).reset_index()
    stats.columns = ['item_count', 'mean_time', 'std_time']
    df_outliers = pd.merge(df_orders, stats, on='item_count', how='left')
    df_outliers['z_score'] = (df_outliers['processing_time_mins'] - df_outliers['mean_time']) / df_outliers['std_time']

    outliers_df = df_outliers[df_outliers['z_score'] > 2].sort_values(by='z_score', ascending=False).head(20)
    outliers = []
    for _, r in outliers_df.iterrows():
        outliers.append({
            "order_id": str(r['order_id']),
            "warehouse": str(r.get('warehouse_name', '—')),
            "items": int(r['item_count']),
            "time": round(float(r['processing_time_mins']), 2),
            "expected": round(float(r['mean_time']), 2),
            "z": round(float(r['z_score']), 2)
        })

    # --- PHASE 4: Electronics Category Chart ---
    keywords = ['Laptop', 'Smart Phone', 'Washing Machine', 'AC', 'Air Conditioner', 'Refrigerator', 'Fridge', 'TV',
                'Television', 'Microwave', 'OTG', 'Coffee Machine']
    pattern = '|'.join(keywords)

    # Filter out top 5% extreme outliers
    p95 = df['processing_time_mins'].quantile(0.95)
    df_filtered = df[df['processing_time_mins'] <= p95].copy()
    df_filtered['time_per_item'] = df_filtered['processing_time_mins'] / df_filtered['item_count']

    df_elec = df_filtered[df_filtered['product_title'].str.contains(pattern, case=False, na=False)].dropna(
        subset=['time_per_item'])
    median_order = df_elec.groupby('product_title')['time_per_item'].median().sort_values(ascending=False).head(
        15)  # Top 15 to keep chart clean

    categories = []
    for prod, med in median_order.items():
        categories.append({"label": str(prod), "value": round(float(med), 2)})

    # --- PHASE 5: Mixed vs Pure Orders (Target Date Range) ---
    start_date, end_date = '2026-10-09', '2026-10-16'
    df_date = df[(df['real_date'] >= start_date) & (df['real_date'] <= end_date)].copy()
    df_date['time_per_item'] = df_date['processing_time_mins'] / df_date['item_count']
    df_date_orders = df_date.drop_duplicates(subset=['order_id'])

    target_items = ['Smart Phone', 'LED TV', 'Split AC', 'Window AC', 'Laptop', 'Washing Machine']
    mixed_pure = []
    for item in target_items:
        item_df = df_date[df_date['product_title'].str.contains(item, case=False, na=False)]
        order_ids = item_df['order_id'].unique()
        mixed_orders = df_date_orders[df_date_orders['order_id'].isin(order_ids)]
        mixed_median = mixed_orders['time_per_item'].median()

        # Pure calculation
        item_counts = item_df.groupby('order_id').size().reset_index(name='count_in_order')
        merged = pd.merge(mixed_orders, item_counts, on='order_id')
        pure_orders = merged[merged['item_count'] == merged['count_in_order']]
        pure_median = pure_orders['time_per_item'].median()

        mixed_pure.append({
            "item": item,
            "mixed_median": round(float(mixed_median), 2) if pd.notna(mixed_median) else 0,
            "pure_median": round(float(pure_median), 2) if pd.notna(pure_median) else 0
        })

    # Package for Frontend
    return {
        "meta": {"rows": len(df), "identifier": identifier},
        "scatter": {"points": scatter_points, "trend": trend_data},
        "summary": summary,
        "outliers": outliers,
        "categories": categories,
        "mixed_pure": mixed_pure
    }