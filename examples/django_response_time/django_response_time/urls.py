from django.conf.urls import include, url

import my_app.urls

urlpatterns = [
    url(r'^.*$', include(my_app.urls)),
]
