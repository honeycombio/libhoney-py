import logging

G_CLIENT = None
WARNED_UNINITIALIZED = False

def warn_uninitialized():
    # warn once if we attempt to use the global state before initialized
    log = logging.getLogger(__name__)
    global WARNED_UNINITIALIZED
    if not WARNED_UNINITIALIZED:
        log.warn("global libhoney method used before initialization")
        WARNED_UNINITIALIZED = True