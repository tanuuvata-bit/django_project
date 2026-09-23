from django.shortcuts import render
from pymongo import MongoClient

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

# def display_data(request):
#     # Connect to MongoDB
#     client = MongoClient('mongodb://localhost:27017/')
#     db = client['django_db']
#     collection = db['csv_records']
#
#     # Query 100 documents (excluding _id)
#     records = list(collection.find({}, {'_id': 0}).limit(100))
#
#     return render(request, 'display.html', {'records': records})


def display_data(request):
    client = MongoClient('mongodb://localhost:27017/')
    db = client['django_db']
    collection = db['csv_records']

    records = list(collection.find({}, {'_id': 0}).limit(100))

    return render(request, 'right_content/display.html', {'records': records})

# ============================================================
# NEW: Bulk Upload / List / Display Orders
# ============================================================
import csv
import io
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django_admin.models import OrderRecord

#another previous code example: hard coded columns
# def bulk_upload(request):
#     if request.method == "POST":
#         csv_file   = request.FILES.get("csv_file")
#         identifier = request.POST.get("identifier", "").strip()
#         overwrite  = request.POST.get("overwrite") == "on"
#
#         if not csv_file:
#             messages.error(request, "Please choose a CSV file.")
#             return redirect("bulk_upload")
#         if not csv_file.name.lower().endswith(".csv"):
#             messages.error(request, "Only .csv files are allowed.")
#             return redirect("bulk_upload")
#         if not identifier:
#             messages.error(request, "Identifier is required.")
#             return redirect("bulk_upload")
#
#         existing = OrderRecord.objects(identifier=identifier).count()
#         if existing > 0:
#             if not overwrite:
#                 messages.error(
#                     request,
#                     f"Identifier '{identifier}' already exists with {existing:,} rows. "
#                     f"Tick 'Overwrite existing' to replace it."
#                 )
#                 return redirect("bulk_upload")
#             OrderRecord.objects(identifier=identifier).delete()
#             messages.info(request, f"Replaced existing data for '{identifier}'.")
#
#         try:
#             decoded = csv_file.read().decode("utf-8", errors="replace")
#             reader  = csv.DictReader(io.StringIO(decoded))
#             rows    = list(reader)
#         except Exception as e:
#             messages.error(request, f"Failed to read CSV: {e}")
#             return redirect("bulk_upload")
#
#         if not rows:
#             messages.warning(request, "CSV file appears to be empty.")
#             return redirect("bulk_upload")
#
#         def parse_dt(s):
#             if not s: return None
#             try:
#                 return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
#             except Exception:
#                 return None
#
#         def parse_float(s):
#             try:
#                 return float(s) if s else None
#             except Exception:
#                 return None
#
#         batch, inserted, CHUNK = [], 0, 5000
#         now = datetime.utcnow()
#
#         for row in rows:
#             record = OrderRecord(
#                 identifier=identifier,
#                 order_id=str(row.get("order_id", "")).strip() or None,
#                 status_name=(row.get("status_name") or "").strip() or None,
#                 status_date=parse_dt((row.get("status_date") or "").strip()),
#                 pincode=str(row.get("pincode", "")).strip() or None,
#                 city=(row.get("city") or "").strip() or None,
#                 latitude=parse_float(row.get("latitude")),
#                 longitude=parse_float(row.get("longitude")),
#                 customer_address=(
#                     (row.get("cutomeraddress") or row.get("customer_address") or "").strip() or None
#                 ),
#                 state_name=(row.get("name") or "").strip() or None,
#                 order_creation_date=parse_dt((row.get("Order Creation date") or "").strip()),
#                 raw={k: v for k, v in row.items() if v},
#                 uploaded_at=now,
#             )
#             batch.append(record)
#             if len(batch) >= CHUNK:
#                 OrderRecord.objects.insert(batch)
#                 inserted += len(batch)
#                 batch = []
#
#         if batch:
#             OrderRecord.objects.insert(batch)
#             inserted += len(batch)
#
#         messages.success(request, f"✅ Uploaded {inserted:,} rows under '{identifier}'.")
#         return redirect(f"/orders/display/?identifier={identifier}")
#
#     recent_ids = sorted(OrderRecord.objects.distinct("identifier"))
#     return render(request, "right_content/bulk_upload.html", {
#         "recent_identifiers": recent_ids[:10],
#     })


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

#previous code with csv based column listing : hard coded column
# def display_orders(request):
#     identifier = request.GET.get("identifier", "").strip()
#     all_ids = sorted(OrderRecord.objects.distinct("identifier"))
#
#     if not identifier:
#         return render(request, "right_content/display_orders.html", {
#             "all_ids": all_ids, "identifier": "",
#             "page_obj": None, "total_orders": 0,
#         })
#
#     city_filter   = request.GET.get("city", "").strip()
#     status_filter = request.GET.get("status", "").strip()
#
#     query = OrderRecord.objects(identifier=identifier)
#     if city_filter:   query = query.filter(city__icontains=city_filter)
#     if status_filter: query = query.filter(status_name__iexact=status_filter)
#
#     total_orders = query.count()
#     page_obj = Paginator(query.order_by("order_id"), 50).get_page(request.GET.get("page", 1))
#
#     return render(request, "right_content/display_orders.html", {
#         "all_ids": all_ids, "identifier": identifier,
#         "page_obj": page_obj, "total_orders": total_orders,
#         "city_filter": city_filter, "status_filter": status_filter,
#     })
# ============================================================
# PAGE 1 — Bulk Upload (schema-agnostic)
# ============================================================
def bulk_upload(request):
    if request.method == "POST":
        csv_file   = request.FILES.get("csv_file")
        identifier = request.POST.get("identifier", "").strip()
        overwrite  = request.POST.get("overwrite") == "on"

        if not csv_file:
            messages.error(request, "Please choose a CSV file.")
            return redirect("bulk_upload")
        if not csv_file.name.lower().endswith(".csv"):
            messages.error(request, "Only .csv files are allowed.")
            return redirect("bulk_upload")
        if not identifier:
            messages.error(request, "Identifier is required.")
            return redirect("bulk_upload")

        existing = OrderRecord.objects(identifier=identifier).count()
        if existing > 0:
            if not overwrite:
                messages.error(
                    request,
                    f"Identifier '{identifier}' already exists with {existing:,} rows. "
                    f"Tick 'Overwrite existing' to replace it."
                )
                return redirect("bulk_upload")
            OrderRecord.objects(identifier=identifier).delete()
            messages.info(request, f"Replaced existing data for '{identifier}'.")

        try:
            decoded = csv_file.read().decode("utf-8", errors="replace")
            reader  = csv.DictReader(io.StringIO(decoded))
            rows    = list(reader)
        except Exception as e:
            messages.error(request, f"Failed to read CSV: {e}")
            return redirect("bulk_upload")

        if not rows:
            messages.warning(request, "CSV file appears to be empty.")
            return redirect("bulk_upload")

        batch, inserted, CHUNK = [], 0, 5000
        now = datetime.utcnow()

        for row in rows:
            record = OrderRecord(
                identifier=identifier,
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


# ============================================================
# PAGE 3 — Display Orders (dynamic columns from CSV)
# ============================================================
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

    # Read column names from the first row of this identifier
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


