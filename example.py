'''This example shows how to use some of the features of libhoney in python'''

import libhoney
import signal
import threading

writekey = "abcabc123123defdef456456"
dataset = "factorial"


def factorial(n):
    if n < 0:
        return -1 * factorial(abs(n))
    if n == 0:
        return 1
    return n * factorial(n - 1)


def num_threads():
    '''add information about the number of threads currently running to the
       event'''
    return threading.activeCount()


# run factorial. libh_builder comes with some fields already populated
# (namely, "version", "num_threads", and "range")
def run_fact(low, high, libh_builder):
    for i in range(low, high):
        ev = libh_builder.new_event()
        ev.metadata = {"fn": "run_fact", "i": i}
        with ev.timer("fact"):
            res = factorial(10 + i)
            ev.add_field("retval", res)
        ev.send()
        print("About to send event: %s" % ev)


def read_responses(resp_queue):
    '''read responses from the libhoney queue, print them out.'''
    while True:
        resp = resp_queue.get()
        if resp is None:
            break
        status = "sending event with metadata {} took {}ms and got response code {} with message \"{}\"".format(
            resp["metadata"], resp["duration"], resp["status_code"],
            resp["body"].rstrip())
        print status


def graceful_shutdown(signum, frame):
    libhoney.close()


if __name__ == "__main__":
    libhoney.init(writekey=writekey, dataset=dataset, max_concurrent_batches=1)
    resps = libhoney.responses()
    t = threading.Thread(target=read_responses, args=(resps,))
    t.start()

    # shut down gracefully
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # attach fields to top-level instance
    libhoney.add_field("version", "3.4.5")
    libhoney.add_dynamic_field(num_threads)

    # sends an event with "version", "num_threads", and "status" fields
    libhoney.send_now({"status": "starting run"})
    run_fact(1, 2, libhoney.Builder({"range": "low"}))
    run_fact(31, 32, libhoney.Builder({"range": "high"}))

    # sends an event with "version", "num_threads", and "status" fields
    libhoney.send_now({"status": "ending run"})
    graceful_shutdown(None, None)
