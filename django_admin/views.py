from django.shortcuts import render

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







