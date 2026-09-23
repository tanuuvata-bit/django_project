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