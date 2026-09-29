# # django_admin/models.py
# from mongoengine import Document, StringField, DateTimeField, FloatField, DictField
#
#
# class OrderRecord(Document):
#     """A single row from an uploaded CSV, tagged with a user-provided identifier."""
#     identifier   = StringField(required=True, index=True)
#     order_id     = StringField(index=True)
#     status_name  = StringField()
#     status_date  = DateTimeField()
#     pincode      = StringField()
#     city         = StringField(index=True)
#     latitude     = FloatField()
#     longitude    = FloatField()
#     customer_address = StringField()
#     state_name   = StringField(db_field="name")
#     order_creation_date = DateTimeField()
#
#     # Preserve any unmapped CSV columns
#     raw = DictField()
#     uploaded_at = DateTimeField()
#
#     meta = {
#         "collection": "orders",
#         "indexes": [
#             "identifier",
#             ("identifier", "order_id"),
#             ("identifier", "city"),
#             ("identifier", "status_name"),
#             "-uploaded_at",
#         ],
#         "ordering": ["-uploaded_at"],
#     }
# django_admin/models.py
from mongoengine import Document, StringField, DateTimeField, DictField


class OrderRecord(Document):
    """One row from any uploaded CSV. Stores all columns in `raw`."""
    identifier  = StringField(required=True, index=True)
    raw         = DictField()       # every CSV column lives here
    uploaded_at = DateTimeField()

    meta = {
        "collection": "orders",
        "indexes": ["identifier"],
        "ordering": ["-uploaded_at"],
    }

from mongoengine import (
    Document, StringField, DateTimeField, ListField
)


class Vehicle(Document):
    # Matches your add_vehicle.html form exactly
    vehicle_id          = StringField(required=True, unique=True, index=True)  # e.g. VEH-101
    vehicle_name        = StringField()                                        # e.g. Tata Ace
    license_plate       = StringField()                                        # e.g. DL01AB1234
    assigned_picker     = StringField()                                        # e.g. picker_1
    payload_capacity_kg = StringField()                                        # keep as string for flexibility
    fuel_type           = StringField()                                        # Diesel/Petrol/EV/CNG
    status              = StringField(default="Active")                        # Active/Maintenance/Inactive
    created_at          = DateTimeField()

    meta = {
        "collection": "vehicles",
        "indexes": ["vehicle_id", "-created_at"],
        "ordering": ["-created_at"],
    }


class Warehouse(Document):
    # Matches your add_warehouse.html form exactly
    warehouse_id           = StringField(required=True, unique=True, index=True)  # WH-NORTH-01
    warehouse_name         = StringField()
    location_address       = StringField()
    assigned_vehicle_ids   = ListField(StringField())                             # multi-select
    assigned_picker_ids    = ListField(StringField())                             # multi-select
    manager_contact        = StringField()
    is_active              = StringField(default="true")                          # "true"/"false"
    created_at             = DateTimeField()

    meta = {
        "collection": "warehouses",
        "indexes": ["warehouse_id", "-created_at"],
        "ordering": ["-created_at"],
    }