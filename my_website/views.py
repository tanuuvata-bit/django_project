from django.shortcuts import render

def home_page(request):
    # This tells Django to render the index.html file we created
    return render(request, 'index.html')