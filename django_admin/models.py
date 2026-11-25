# django_admin/models.py
from mongoengine import Document, StringField, DateTimeField, DictField, ListField

class OrderRecord(Document):
    """One row from any uploaded CSV/JSON. Stores all columns in `raw`."""
    identifier  = StringField(required=True, index=True)
    file_type   = StringField(default="generic_csv")
    original_filename = StringField() # <--- NEW: Tracks the exact file name
    raw         = DictField()
    uploaded_at = DateTimeField()

    meta = {
        "collection": "orders",
        "indexes": ["identifier"],
        "ordering": ["-uploaded_at"],
    }

class Vehicle(Document):
    vehicle_id          = StringField(required=True, unique=True, index=True)
    vehicle_name        = StringField()
    license_plate       = StringField()
    assigned_picker     = StringField()
    payload_capacity_kg = StringField()
    fuel_type           = StringField()
    status              = StringField(default="Active")
    created_at          = DateTimeField()

    meta = {
        "collection": "vehicles",
        "indexes": ["vehicle_id", "-created_at"],
        "ordering": ["-created_at"],
    }

class Warehouse(Document):
    warehouse_id           = StringField(required=True, unique=True, index=True)
    warehouse_name         = StringField()
    location_address       = StringField()
    assigned_vehicle_ids   = ListField(StringField())
    assigned_picker_ids    = ListField(StringField())
    manager_contact        = StringField()
    is_active              = StringField(default="true")
    created_at             = DateTimeField()

    meta = {
        "collection": "warehouses",
        "indexes": ["warehouse_id", "-created_at"],
        "ordering": ["-created_at"],
    }