# my_website/analytics/registry.py
from .engine import analyze_identifier
from .sales_engine import analyze_sales
from .route_planning_engine import analyze_route_planning
from .three_csv_engine import analyze_three_csv  # <--- Import

def get_engine_for_file(file_type):
    if file_type == "route_json":
        return analyze_route_planning
    elif file_type == "sales_csv":
        return analyze_sales
    elif file_type == "three_csv_route":   # <--- Route
        return analyze_three_csv
    elif file_type == "generic_csv":
        return analyze_identifier
    return analyze_identifier