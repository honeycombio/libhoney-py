import os
import time
import libhoney


class HoneyMiddleware(object):
    def __init__(self):
        libhoney.init(writekey=os.environ["HONEY_WRITE_KEY"],
                      dataset=os.environ["HONEY_DATASET"])


    def process_request(self, request):
        request.start_time = time.time()

        return None


    def process_response(self, request, response):
        response_time = time.time() - request.start_time

        libhoney.send_now({
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
            "responseTime_ms": response_time * 1000,
        })

        return response

