import os

import libhoney


class HoneyMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        libhoney.init(writekey=os.environ["HONEYCOMB_API_KEY"],
                      dataset=os.environ.get("HONEYCOMB_DATASET", "django-example"),
                      api_host=os.environ.get("HONEYCOMB_API_ENDPOINT", "https://api.honeycomb.io"))

    def __call__(self, request):
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        ev = libhoney.new_event(data={
            "method": request.method,
            "scheme": request.scheme,
            "path": request.path,
            "query": request.GET,
            "isSecure": request.is_secure(),
            "isAjax": is_ajax,
            "isUserAuthenticated": request.user.is_authenticated,
            "username": request.user.username,
            "host": request.get_host(),
            "ip": request.META['REMOTE_ADDR'],
        })
        ev.send()

        response = self.get_response(request)
        return response
