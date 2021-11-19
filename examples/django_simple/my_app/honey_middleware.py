import os
import libhoney


class HoneyMiddleware(object):
    def __init__(self):
        libhoney.init(writekey=os.environ["HONEYCOMB_API_KEY"],
                      dataset=os.environ["HONEYCOMB_DATASET"])


    def process_request(self, request):
        ev = libhoney.new_event(data={
            "method": request.method,
            "scheme": request.scheme,
            "path": request.path,
            "query": request.GET,
            "isSecure": request.is_secure(),
            "isAjax": request.is_ajax(),
            "isUserAuthenticated": request.user.is_authenticated(),
            "username": request.user.username,
            "host": request.get_host(),
            "ip": request.META['REMOTE_ADDR'],
        })
        ev.send()

        return None

