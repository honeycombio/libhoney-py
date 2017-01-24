import os
import resource
import libhoney


class HoneyMiddleware(object):
    def __init__(self):
        libhoney.init(writekey=os.environ["HONEY_WRITE_KEY"],
                      dataset=os.environ["HONEY_DATASET"])


    def process_request(self, request):

        def usertime_after():
            return resource.getrusage(resource.RUSAGE_SELF).ru_utime

        def kerneltime_after():
            return resource.getrusage(resource.RUSAGE_SELF).ru_stime

        def maxrss_after():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        request.honey_builder = libhoney.Builder({
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

            "usertime_before": resource.getrusage(resource.RUSAGE_SELF).ru_utime,
            "kerneltime_before": resource.getrusage(resource.RUSAGE_SELF).ru_stime,
            "maxrss_before": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }, [
            usertime_after,
            kerneltime_after,
            maxrss_after,
        ])

        return None


    def process_response(self, request, response):
        builder = request.honey_builder
        ev = builder.new_event()
        ev.send()

        return response

