import libhoney
from libhoney import trace_call

def fib(n):
    if n == 0: return 0
    elif n == 1: return 1
    else: 
        return trace_call(fib, n-1, trace_name="fib %d" % (n-1)) + \
               trace_call(fib, n-2, trace_name="fib %d" % (n-2))

def main():
    trace_call(fib, 1, trace_name="fib 1", service_name="fabulous fibonacci")
    trace_call(fib, 5, trace_name="fib 5", service_name="fabulous fibonacci")
    trace_call(fib, 10, trace_name="fib 10", service_name="fabulous fibonacci")

if __name__ == "__main__":
    libhoney.init(writekey='abcdefghijklmnopqrstuvwxyz', dataset='fibonacci')
    try:
        trace_call(main)
    except Exception as e:
        print(e)
    libhoney.close()
