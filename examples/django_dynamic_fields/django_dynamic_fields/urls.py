from django.urls import path, include

urlpatterns = [
    path('', include('my_app.urls')),
]
