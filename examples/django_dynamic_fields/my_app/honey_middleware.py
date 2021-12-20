import os
import resource

import libhoney


class HoneyMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        libhoney.init(writekey=os.environ["HONEYCOMB_API_KEY"],
                      dataset=os.environ.get("HONEYCOMB_DATASET", "django-example"),
                      api_host=os.environ.get("HONEYCOMB_API_ENDPOINT", "https://api.honeycomb.io"))

    def __call__(self, request):
        def usertime_after():
            return resource.getrusage(resource.RUSAGE_SELF).ru_utime

        def kerneltime_after():
            return resource.getrusage(resource.RUSAGE_SELF).ru_stime

        def maxrss_after():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        honey_builder = libhoney.Builder({
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

            "usertime_before": resource.getrusage(resource.RUSAGE_SELF).ru_utime,
            "kerneltime_before": resource.getrusage(resource.RUSAGE_SELF).ru_stime,
            "maxrss_before": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }, [
            usertime_after,
            kerneltime_after,
            maxrss_after,
        ])
        response = self.get_response(request)
        # creating new event will call the dynamic fields functions
        event = honey_builder.new_event()
        event.send()

        return response
