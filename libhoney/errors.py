class SendError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

class NotInitializedError(Exception):
    '''raised when global methods are called before calling init'''
    pass
