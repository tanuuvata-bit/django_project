"""
URL configuration for django_admin project.
"""
from django.contrib import admin
from django.urls import path, include
from . import views
from .views import display_data

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- existing pages ---
    path("", views.index, name="index"),
    path("upload-order-form",   views.upload_order_form,  name="upload_order_form"),
    path("upload-order-form-1", views.upload_order_form1, name="upload_order_form_1"),
    path("add_drivers",    views.add_drivers,    name="add_drivers"),
    path("list_drivers",   views.list_drivers,   name="list_drivers"),
    path("driver_details", views.driver_details, name="driver_details"),
    path("on_demand",      views.on_demand,      name="on_demand"),
    path("e_commerce",     views.e_commerce,     name="e_commerce"),
    path("active_routes",  views.active_routes,  name="active_routes"),
    path("add_trip",       views.add_trip,       name="add_trip"),
    path("failed",         views.failed,         name="failed"),
    path("add_hub",        views.add_hub,        name="add_hub"),
    path("delete_hub",     views.delete_hub,     name="delete_hub"),
    path("list_hubs",      views.list_hubs,      name="list_hubs"),
    path("pin_code",       views.pin_code,       name="pin_code"),
    path('display/', display_data, name='display_data'),

    # --- NEW: Bulk Upload / List / Display Orders ---
    path("orders/bulk-upload/", views.bulk_upload,      name="bulk_upload"),
    path("orders/list/",        views.list_identifiers, name="list_identifiers"),
    path("orders/display/",     views.display_orders,   name="display_orders"),
    path("orders/delete/<str:identifier>/",
         views.delete_identifier, name="delete_identifier"),
    # --- NEW: Add Vehicle / Add Warehouse ---
    path("add_vehicle/", views.add_vehicle, name="add_vehicle"),
    path("add_warehouse/", views.add_warehouse, name="add_warehouse"),
    #---- Analysis is added
    path("analysis/", views.analysis_page, name="analysis_page"),
    path("api/summary/<str:identifier>/", views.api_analysis_summary, name="api_analysis_summary"),
    path("api/refresh/<str:identifier>/", views.api_analysis_refresh, name="api_analysis_refresh"),
    #-----List vehicle and list warehouse
    path("add_vehicle", views.add_vehicle, name="add_vehicle"),
    path("list_vehicles", views.list_vehicles, name="list_vehicles"),
    path("delete_vehicle/<str:vehicle_id>", views.delete_vehicle, name="delete_vehicle"),
    # Vehicle edit
    path("edit_vehicle/<str:vehicle_id>", views.edit_vehicle, name="edit_vehicle"),

    path("add_warehouse", views.add_warehouse, name="add_warehouse"),
    path("list_warehouses", views.list_warehouses, name="list_warehouses"),
    path("delete_warehouse/<str:warehouse_id>", views.delete_warehouse, name="delete_warehouse"),
    # Warehouse edit
    path("edit_warehouse/<str:warehouse_id>", views.edit_warehouse, name="edit_warehouse"),



]