# my_website/analytics/sales_engine.py
import pandas as pd
import numpy as np
from datetime import datetime
from django_admin.models import OrderRecord

def analyze_sales(identifier: str) -> dict:
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

    phases = []

    # --- PHASE 1: Order Level Scatter ---
    df_orders = df.drop_duplicates(subset=['order_id']).copy()
    df_orders = df_orders[(df_orders['processing_time_mins'] > 0) & (df_orders['item_count'] > 0)]
    df_orders['time_per_item'] = df_orders['processing_time_mins'] / df_orders['item_count']

    scatter_data = df_orders[['item_count', 'processing_time_mins']].dropna()
    scatter_sample = scatter_data.sample(min(1000, len(scatter_data)), random_state=42)
    scatter_points = [{"x": float(r['item_count']), "y": float(r['processing_time_mins'])} for _, r in scatter_sample.iterrows()]

    try:
        z = np.polyfit(scatter_data['item_count'], scatter_data['processing_time_mins'], 1)
        p = np.poly1d(z)
        x_min, x_max = scatter_data['item_count'].min(), scatter_data['item_count'].max()
        trend_data = [{"x": float(x_min), "y": float(p(x_min))}, {"x": float(x_max), "y": float(p(x_max))}]
    except Exception:
        trend_data = []

    phases.append({
        "name": "scatter_chart",
        "chart": "scatter",
        "title": "Item Count vs Processing Time",
        "points": scatter_points,
        "trend": trend_data
    })

    # --- PHASE 2: Summary by Item Range ---
    bins = [0, 2, 5, 10, 20, 100]
    labels = ['1-2 items', '3-5 items', '6-10 items', '11-20 items', '20+ items']
    df_orders['item_range'] = pd.cut(df_orders['item_count'], bins=bins, labels=labels)

    summary_rows = []
    for label in labels:
        sub = df_orders[df_orders['item_range'] == label]
        if len(sub) > 0:
            summary_rows.append([
                label,
                int(len(sub)),
                round(float(sub['processing_time_mins'].mean()), 2),
                round(float(sub['processing_time_mins'].min()), 2),
                round(float(sub['processing_time_mins'].max()), 2),
                round(float(np.percentile(sub['processing_time_mins'], 95)), 2),
                round(float(sub['time_per_item'].mean()), 2)
            ])

    phases.append({
        "name": "summary_table",
        "chart": "table",
        "title": "Summary Statistics by Item Range",
        "headers": ["Item Range", "Total Orders", "Avg Time", "Min", "Max", "95th %ile", "Avg Time / Item"],
        "rows": summary_rows
    })

    # --- PHASE 3: Z-Score Outliers ---
    stats = df_orders.groupby('item_count')['processing_time_mins'].agg(['mean', 'std']).reset_index()
    stats.columns = ['item_count', 'mean_time', 'std_time']
    df_outliers = pd.merge(df_orders, stats, on='item_count', how='left')
    df_outliers['z_score'] = (df_outliers['processing_time_mins'] - df_outliers['mean_time']) / df_outliers['std_time']

    outliers_df = df_outliers[df_outliers['z_score'] > 2].sort_values(by='z_score', ascending=False).head(20)
    outlier_rows = []
    for _, r in outliers_df.iterrows():
        outlier_rows.append([
            f"<strong>{r['order_id']}</strong>",
            str(r.get('warehouse_name', '—')),
            int(r['item_count']),
            f"{round(float(r['processing_time_mins']), 2)} mins",
            f"{round(float(r['mean_time']), 2)} mins",
            f"+{round(float(r['z_score']), 2)}σ"
        ])

    phases.append({
        "name": "outliers_table",
        "chart": "table",
        "title": "Outlier Traceability (Z-Score > 2)",
        "headers": ["Order ID", "Warehouse", "Items", "Actual Time", "Expected", "Z-Score"],
        "rows": outlier_rows
    })

    # --- PHASE 4: Electronics Category Chart ---
    keywords = ['Laptop', 'Smart Phone', 'Washing Machine', 'AC', 'Air Conditioner', 'Refrigerator', 'Fridge', 'TV', 'Television', 'Microwave', 'OTG', 'Coffee Machine']
    pattern = '|'.join(keywords)

    p95 = df['processing_time_mins'].quantile(0.95)
    df_filtered = df[df['processing_time_mins'] <= p95].copy()
    df_filtered['time_per_item'] = df_filtered['processing_time_mins'] / df_filtered['item_count']

    df_elec = df_filtered[df_filtered['product_title'].str.contains(pattern, case=False, na=False)].dropna(subset=['time_per_item'])
    median_order = df_elec.groupby('product_title')['time_per_item'].median().sort_values(ascending=False).head(15)

    cat_labels, cat_values = [], []
    for prod, med in median_order.items():
        cat_labels.append(str(prod))
        cat_values.append(round(float(med), 2))

    if cat_labels:
        phases.append({
            "name": "category_chart",
            "chart": "h_bar",
            "title": "Median Time PER ITEM by Electronic Item",
            "labels": cat_labels,
            "values": cat_values,
            "color": "#10b981",
            "suffix": " mins"
        })

    # --- PHASE 5: Mixed vs Pure Orders (Target Date Range) ---
    start_date, end_date = '2026-10-09', '2026-10-16'
    df_date = df[(df['real_date'] >= start_date) & (df['real_date'] <= end_date)].copy()
    df_date['time_per_item'] = df_date['processing_time_mins'] / df_date['item_count']
    df_date_orders = df_date.drop_duplicates(subset=['order_id'])

    target_items = ['Smart Phone', 'LED TV', 'Split AC', 'Window AC', 'Laptop', 'Washing Machine']
    mixed_rows = []
    for item in target_items:
        item_df = df_date[df_date['product_title'].str.contains(item, case=False, na=False)]
        order_ids = item_df['order_id'].unique()
        mixed_orders = df_date_orders[df_date_orders['order_id'].isin(order_ids)]
        mixed_median = mixed_orders['time_per_item'].median()

        item_counts = item_df.groupby('order_id').size().reset_index(name='count_in_order')
        merged = pd.merge(mixed_orders, item_counts, on='order_id')
        pure_orders = merged[merged['item_count'] == merged['count_in_order']]
        pure_median = pure_orders['time_per_item'].median()

        mixed_rows.append([
            f"<strong>{item}</strong>",
            f"{round(float(mixed_median), 2)} mins" if pd.notna(mixed_median) else "—",
            f"{round(float(pure_median), 2)} mins" if pd.notna(pure_median) else "—"
        ])

    phases.append({
        "name": "mixed_pure_table",
        "chart": "table",
        "title": "Mixed vs Pure Orders (Oct 9 - Oct 16)",
        "headers": ["Item", "Mixed Order Median", "Pure Order Median"],
        "rows": mixed_rows
    })

    # --- RETURN STANDARD STRUCTURE ---
    return {
        "identifier": identifier,
        "computed_at": datetime.utcnow().isoformat(),
        "meta": {"rows": len(df)},
        "phases": phases
    }