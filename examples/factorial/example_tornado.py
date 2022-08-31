import os
from tornado import ioloop, gen
import libhoney
from libhoney.transmission import TornadoTransmission

g_hc = None

def factorial(n):
    if n < 0:
        return -1 * factorial(abs(n))
    if n == 0:
        return 1
    return n * factorial(n - 1)

def run_fact(low, high, libh_builder):
    for i in range(low, high):
        ev = libh_builder.new_event()
        ev.metadata = {"fn": "run_fact", "i": i}
        with ev.timer("fact_timer"):
            res = factorial(10 + i)
            ev.add_field("retval", res)
        ev.send()
        print("About to send event: %s" % ev)

@gen.coroutine
def event_routine():
    event_counter = 1
    while event_counter <= 100:
        run_fact(1, event_counter, g_hc.new_builder({"event_counter": event_counter}))

        event_counter += 1
        yield gen.sleep(0.1)

@gen.coroutine
def main():
    global g_hc
    g_hc = libhoney.Client(writekey=os.environ["HONEYCOMB_API_KEY"], dataset="factorial.tornado",
        transmission_impl=TornadoTransmission())
    ioloop.IOLoop.current().spawn_callback(event_routine)

    while True:
        r = yield g_hc.responses().get()
        print("Got response: %s" % r)

if __name__ == "__main__":
    ioloop.IOLoop.current().run_sync(main)

