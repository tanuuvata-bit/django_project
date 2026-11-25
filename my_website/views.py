from django.shortcuts import render
from pymongo import MongoClient
from django.http import JsonResponse
from bson import ObjectId
from django.core.cache import cache
from django_admin.models import OrderRecord
from django.utils import timezone
from django_admin.models import Vehicle, Warehouse
from my_website.analytics.registry import get_engine_for_file
import csv
import io
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator


def index(request):
    return render(request, 'layout/body.html')


def upload_order_form(request):
    return render(request, 'right_content/upload_order_frm.html')


def upload_order_form1(request):
    return render(request, 'right_content/upload_order_frm_1.html')


def add_drivers(request):
    return render(request, 'right_content/add_drivers.html')


def list_drivers(request):
    return render(request, 'right_content/list_drivers.html')


def driver_details(request):
    return render(request, 'right_content/driver_details.html')


def on_demand(request):
    return render(request, 'right_content/on_demand.html')


def e_commerce(request):
    return render(request, 'right_content/e_commerce.html')


def active_routes(request):
    return render(request, 'right_content/active_routes.html')


def add_trip(request):
    return render(request, 'right_content/add_trip.html')


def failed(request):
    return render(request, 'right_content/failed.html')


def add_hub(request):
    return render(request, 'right_content/add_hub.html')


def delete_hub(request):
    return render(request, 'right_content/delete_hub.html')


def list_hubs(request):
    return render(request, 'right_content/list_hubs.html')


def pin_code(request):
    return render(request, 'right_content/pin_code.html')


def display_data(request):
    client = MongoClient('mongodb://localhost:27017/')
    db = client['django_db']
    collection = db['csv_records']
    records = list(collection.find({}, {'_id': 0}).limit(100))
    return render(request, 'right_content/display.html', {'records': records})


def list_identifiers(request):
    pipeline = [
        {"$group": {"_id": "$identifier",
                    "count": {"$sum": 1},
                    "uploaded": {"$max": "$uploaded_at"}}},
        {"$sort": {"uploaded": -1}},
    ]
    rows = list(OrderRecord.objects.aggregate(*pipeline))
    identifiers = [
        {"identifier": r["_id"], "count": r["count"], "uploaded_at": r.get("uploaded")}
        for r in rows
    ]
    return render(request, "right_content/list_identifiers.html", {
        "identifiers": identifiers,
    })


# ============================================================
# PAGE 1 — Bulk Upload (Handles BOTH CSV and JSON)
# ============================================================
def bulk_upload(request):
    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        identifier = request.POST.get("identifier", "").strip()
        overwrite = request.POST.get("overwrite") == "on"
        file_type = request.POST.get("file_type", "generic_csv")

        if not csv_file:
            messages.error(request, "Please choose a file.")
            return redirect("bulk_upload")
        if not identifier:
            messages.error(request, "Identifier is required.")
            return redirect("bulk_upload")

        existing = OrderRecord.objects(identifier=identifier).count()
        if existing > 0:
            if not overwrite:
                # NEW: Allow appending for the 3-CSV pipeline
                if file_type == "three_csv_route":
                    pass  # Allow the upload to append to the database
                else:
                    messages.error(
                        request,
                        f"Identifier '{identifier}' already exists with {existing:,} rows. "
                        f"Tick 'Overwrite existing' to replace it."
                    )
                    return redirect("bulk_upload")
            else:
                OrderRecord.objects(identifier=identifier).delete()
                messages.info(request, f"Replaced existing data for '{identifier}'.")

        try:
            decoded = csv_file.read().decode("utf-8", errors="replace")

            # --- JSON PARSING LOGIC ---
            if csv_file.name.lower().endswith(".json") or file_type == "route_json":
                json_data = json.loads(decoded)
                if isinstance(json_data, dict):
                    json_data = [json_data]
                # Wrap in __json__ so MongoEngine DictField accepts it cleanly
                rows = [{"__json__": item} for item in json_data]
            else:
                # --- CSV PARSING LOGIC ---
                reader = csv.DictReader(io.StringIO(decoded))
                rows = list(reader)

        except Exception as e:
            messages.error(request, f"Failed to read file: {e}")
            return redirect("bulk_upload")

        if not rows:
            messages.warning(request, "File appears to be empty.")
            return redirect("bulk_upload")

        batch, inserted, CHUNK = [], 0, 5000
        now = datetime.utcnow()

        for row in rows:
            record = OrderRecord(
                identifier=identifier,
                file_type=file_type,
                raw={k: v for k, v in row.items() if v not in (None, "")},
                uploaded_at=now,
            )
            batch.append(record)
            if len(batch) >= CHUNK:
                OrderRecord.objects.insert(batch)
                inserted += len(batch)
                batch = []

        if batch:
            OrderRecord.objects.insert(batch)
            inserted += len(batch)

        messages.success(request, f"✅ Uploaded {inserted:,} rows under '{identifier}'.")
        return redirect(f"/orders/display/?identifier={identifier}")

    recent_ids = sorted(OrderRecord.objects.distinct("identifier"))
    return render(request, "right_content/bulk_upload.html", {
        "recent_identifiers": recent_ids[:10],
    })


def display_orders(request):
    identifier = request.GET.get("identifier", "").strip()
    all_ids = sorted(OrderRecord.objects.distinct("identifier"))

    if not identifier:
        return render(request, "right_content/display_orders.html", {
            "all_ids": all_ids, "identifier": "",
            "page_obj": None, "total_orders": 0, "columns": [],
        })

    query = OrderRecord.objects(identifier=identifier)
    total_orders = query.count()

    sample = query.first()
    columns = list(sample.raw.keys()) if (sample and isinstance(sample.raw, dict)) else []

    page_obj = Paginator(query.order_by("uploaded_at"), 50).get_page(request.GET.get("page", 1))

    return render(request, "right_content/display_orders.html", {
        "all_ids": all_ids,
        "identifier": identifier,
        "page_obj": page_obj,
        "total_orders": total_orders,
        "columns": columns,
    })


def delete_identifier(request, identifier):
    count = OrderRecord.objects(identifier=identifier).delete()
    messages.success(request, f"Deleted '{identifier}' ({count} rows).")
    return redirect("list_identifiers")


# ============================================================
# VEHICLES & WAREHOUSES
# ============================================================
def list_vehicles(request):
    vehicles = Vehicle.objects().order_by("-created_at")
    return render(request, "right_content/list_vehicles.html", {"vehicles": vehicles})


def delete_vehicle(request, vehicle_id):
    try:
        v = Vehicle.objects(id=ObjectId(vehicle_id)).first()
        if v:
            v.delete()
            messages.success(request, "Vehicle deleted.")
        else:
            messages.warning(request, "Vehicle not found.")
    except Exception as e:
        messages.error(request, f"Failed to delete: {e}")
    return redirect("list_vehicles")


def list_warehouses(request):
    warehouses = Warehouse.objects().order_by("-created_at")
    return render(request, "right_content/list_warehouses.html", {"warehouses": warehouses})


def delete_warehouse(request, warehouse_id):
    try:
        w = Warehouse.objects(id=ObjectId(warehouse_id)).first()
        if w:
            w.delete()
            messages.success(request, "Warehouse deleted.")
        else:
            messages.warning(request, "Warehouse not found.")
    except Exception as e:
        messages.error(request, f"Failed to delete: {e}")
    return redirect("list_warehouses")


def add_vehicle(request):
    if request.method == "POST":
        vehicle_id = request.POST.get("vehicle_id", "").strip()
        if not vehicle_id:
            messages.error(request, "Vehicle ID is required.")
            return redirect("add_vehicle")

        if Vehicle.objects(vehicle_id=vehicle_id).first():
            messages.error(request, f"Vehicle '{vehicle_id}' already exists.")
            return redirect("add_vehicle")

        Vehicle(
            vehicle_id=vehicle_id,
            vehicle_name=request.POST.get("vehicle_name", "").strip() or None,
            license_plate=request.POST.get("license_plate", "").strip() or None,
            assigned_picker=request.POST.get("assigned_picker", "").strip() or None,
            payload_capacity_kg=request.POST.get("payload_capacity_kg", "").strip() or None,
            fuel_type=request.POST.get("fuel_type", "").strip() or None,
            status=request.POST.get("status", "Active"),
            created_at=timezone.now(),
        ).save()

        messages.success(request, f"✅ Vehicle '{vehicle_id}' added.")
        return redirect("list_vehicles")

    return render(request, "right_content/add_vehicle.html")


def add_warehouse(request):
    if request.method == "POST":
        warehouse_id = request.POST.get("warehouse_id", "").strip()
        if not warehouse_id:
            messages.error(request, "Warehouse ID is required.")
            return redirect("add_warehouse")

        if Warehouse.objects(warehouse_id=warehouse_id).first():
            messages.error(request, f"Warehouse '{warehouse_id}' already exists.")
            return redirect("add_warehouse")

        assigned_vehicle_ids = request.POST.getlist("assigned_vehicle_ids")
        assigned_picker_ids = request.POST.getlist("assigned_picker_ids")

        Warehouse(
            warehouse_id=warehouse_id,
            warehouse_name=request.POST.get("warehouse_name", "").strip() or None,
            location_address=request.POST.get("location_address", "").strip() or None,
            assigned_vehicle_ids=assigned_vehicle_ids,
            assigned_picker_ids=assigned_picker_ids,
            manager_contact=request.POST.get("manager_contact", "").strip() or None,
            is_active=request.POST.get("is_active", "true"),
            created_at=timezone.now(),
        ).save()

        messages.success(request, f"✅ Warehouse '{warehouse_id}' added.")
        return redirect("list_warehouses")

    return render(request, "right_content/add_warehouse.html")


def edit_vehicle(request, vehicle_id):
    try:
        vehicle = Vehicle.objects(id=ObjectId(vehicle_id)).first()
    except Exception:
        vehicle = None

    if not vehicle:
        messages.error(request, "Vehicle not found.")
        return redirect("list_vehicles")

    if request.method == "POST":
        new_vehicle_id = request.POST.get("vehicle_id", "").strip()
        if not new_vehicle_id:
            messages.error(request, "Vehicle ID is required.")
            return redirect("edit_vehicle", vehicle_id=vehicle_id)

        if new_vehicle_id != vehicle.vehicle_id:
            if Vehicle.objects(vehicle_id=new_vehicle_id).first():
                messages.error(request, f"Vehicle ID '{new_vehicle_id}' already exists.")
                return redirect("edit_vehicle", vehicle_id=vehicle_id)

        vehicle.vehicle_id = new_vehicle_id
        vehicle.vehicle_name = request.POST.get("vehicle_name", "").strip() or None
        vehicle.license_plate = request.POST.get("license_plate", "").strip() or None
        vehicle.assigned_picker = request.POST.get("assigned_picker", "").strip() or None
        vehicle.payload_capacity_kg = request.POST.get("payload_capacity_kg", "").strip() or None
        vehicle.fuel_type = request.POST.get("fuel_type", "").strip() or None
        vehicle.status = request.POST.get("status", "Active")
        vehicle.save()

        messages.success(request, f"✅ Vehicle '{new_vehicle_id}' updated.")
        return redirect("list_vehicles")

    return render(request, "right_content/edit_vehicle.html", {"vehicle": vehicle})


def edit_warehouse(request, warehouse_id):
    try:
        warehouse = Warehouse.objects(id=ObjectId(warehouse_id)).first()
    except Exception:
        warehouse = None

    if not warehouse:
        messages.error(request, "Warehouse not found.")
        return redirect("list_warehouses")

    if request.method == "POST":
        new_warehouse_id = request.POST.get("warehouse_id", "").strip()
        if not new_warehouse_id:
            messages.error(request, "Warehouse ID is required.")
            return redirect("edit_warehouse", warehouse_id=warehouse_id)

        if new_warehouse_id != warehouse.warehouse_id:
            if Warehouse.objects(warehouse_id=new_warehouse_id).first():
                messages.error(request, f"Warehouse ID '{new_warehouse_id}' already exists.")
                return redirect("edit_warehouse", warehouse_id=warehouse_id)

        assigned_vehicle_ids = request.POST.getlist("assigned_vehicle_ids")
        assigned_picker_ids = request.POST.getlist("assigned_picker_ids")

        warehouse.warehouse_id = new_warehouse_id
        warehouse.warehouse_name = request.POST.get("warehouse_name", "").strip() or None
        warehouse.location_address = request.POST.get("location_address", "").strip() or None
        warehouse.assigned_vehicle_ids = assigned_vehicle_ids
        warehouse.assigned_picker_ids = assigned_picker_ids
        warehouse.manager_contact = request.POST.get("manager_contact", "").strip() or None
        warehouse.is_active = request.POST.get("is_active", "true")
        warehouse.save()

        messages.success(request, f"✅ Warehouse '{new_warehouse_id}' updated.")
        return redirect("list_warehouses")

    return render(request, "right_content/edit_warehouse.html", {"warehouse": warehouse})


# ============================================================
# ANALYSIS PAGE (Unified)
# ============================================================
def analysis_page(request):
    identifiers = sorted(OrderRecord.objects.distinct("identifier"))
    files = [
        {"identifier": ident, "name": ident, "status": "completed"}
        for ident in identifiers
    ]
    return render(request, "right_content/analysis.html", {"files": files})


# my_website/views.py

def api_analysis_summary(request, identifier):
    cache_key = f"analysis_summary:{identifier}"
    cached = cache.get(cache_key)

    # 1. Clear cache if it's not a dictionary (fixes the current bug)
    if cached:
        if not isinstance(cached, dict):
            cache.delete(cache_key)
        else:
            return JsonResponse(cached)

    record = OrderRecord.objects(identifier=identifier).first()
    if not record:
        return JsonResponse({"error": "Identifier not found"}, status=404)

    file_type = getattr(record, 'file_type', 'generic_csv')
    engine_function = get_engine_for_file(file_type)

    try:
        summary = engine_function(identifier)

        # 2. Prevent the engine from crashing the page if it returns a list
        if not isinstance(summary, dict):
            return JsonResponse(
                {"error": "The analysis engine returned an invalid format (not a dict). Please check the engine code."},
                status=500)

        cache.set(cache_key, summary, timeout=3600)
        return JsonResponse(summary)
    except Exception as e:
        return JsonResponse({"error": str(e)[:500]}, status=500)


def api_analysis_refresh(request, identifier):
    cache.delete(f"analysis_summary:{identifier}")
    return JsonResponse({"ok": True, "identifier": identifier})


def delete_order(request, file_id):
    try:
        f = OrderRecord.objects(identifier=file_id).first()
        if f:
            f.delete()
            messages.success(request, f"Order '{file_id}' deleted.")
        else:
            messages.warning(request, f"Order '{file_id}' not found.")
    except Exception as e:
        messages.error(request, f"Failed to delete: {e}")
    return redirect("list_identifiers")