"""
URL configuration for django_admin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("",views.index,name="index"),
    path("upload-order-form", views.upload_order_form, name="upload_order_form"),
    path("upload-order-form-1",  views.upload_order_form1, name="upload_order_form_1"),
    path("add_drivers", views.add_drivers, name="add_drivers"),
    path("list_drivers", views.list_drivers, name="list_drivers"),
    path("driver_details", views.driver_details, name="driver_details"),
    path("on_demand", views.on_demand, name="on_demand"),
    path("e_commerce", views.e_commerce, name="e_commerce"),
    path("active_routes", views.active_routes, name="active_routes"),
    path("add_trip", views.add_trip, name="add_trip"),
    path("failed", views.failed, name="failed"),
    path("add_hub", views.add_hub, name="add_hub"),
    path("delete_hub", views.delete_hub, name="delete_hub"),
    path("list_hubs", views.list_hubs, name="list_hubs"),
    path("pin_code", views.pin_code, name="pin_code"),
]



