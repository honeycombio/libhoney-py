'''This example shows how to use some of the features of libhoney in python'''
import os
import datetime
import libhoney
import threading

writekey=os.environ.get("HONEYCOMB_API_KEY")
dataset=os.environ.get("HONEYCOMB_DATASET", "factorial")
api_host=os.environ.get("HONEYCOMB_API_ENDPOINT", "https://api.honeycomb.io")

def factorial(n):
    if n < 0:
        return -1 * factorial(abs(n))
    if n == 0:
        return 1
    return n * factorial(n - 1)


def num_threads():
    '''add information about the number of threads currently running to the
       event'''
    return threading.active_count()


# run factorial. libh_builder comes with some fields already populated
# (namely, "version", "num_threads", and "range")
def run_fact(low, high, libh_builder):
    for i in range(low, high):
        ev = libh_builder.new_event()
        ev.metadata = {"fn": "run_fact", "i": i}
        with ev.timer("fact"):
            res = factorial(10 + i)
            ev.add_field("retval", res)
        print("About to send event: %s" % ev)
        ev.send()


def read_responses(resp_queue):
    '''read responses from the libhoney queue, print them out.'''
    while True:
        resp = resp_queue.get()
        # libhoney will enqueue a None value after we call libhoney.close()
        if resp is None:
            break
        status = "sending event with metadata {} took {}ms and got response code {} with message \"{}\" and error message \"{}\"".format(
            resp["metadata"], resp["duration"], resp["status_code"],
            resp["body"].rstrip(), resp["error"])
        print(status)


if __name__ == "__main__":
    hc = libhoney.Client(writekey=writekey,
                        dataset=dataset,
                        api_host=api_host,
                        max_concurrent_batches=1)
    resps = hc.responses()
    t = threading.Thread(target=read_responses, args=(resps,))

    # Mark this thread as a daemon so we don't wait for this thread to exit
    # before shutting down.  Alternatively, to be sure you read all the
    # responses before exiting, omit this line and explicitly call
    # libhoney.close() at the end of the script.
    t.daemon = True

    t.start()

    # Attach fields to top-level instance
    hc.add_field("version", "3.4.5")
    hc.add_dynamic_field(num_threads)

    ev = hc.new_event()
    ev.add_field("start_time", datetime.datetime.now().isoformat())

    # wrap our calls with timers
    with ev.timer(name="run_fact_1_2_dur_ms"):
        run_fact(1, 2, hc.new_builder({"range": "low"}))
    with ev.timer(name="run_fact_31_32_dur_ms"):
        run_fact(31, 32, hc.new_builder({"range": "high"}))
    ev.add_field("end_time", datetime.datetime.now().isoformat())
    # sends event with fields: version, num_threads, start_time, end_time,
    # run_fact_1_2_dur_ms, run_fact_31_32_dur_ms
    ev.send()

    # Optionally tell libhoney there are no more events coming.  This ensures
    # the read_responses thread will terminate.
    hc.close()
