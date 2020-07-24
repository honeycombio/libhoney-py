def json_default_handler(obj):
    ''' this function handles values that the json encoder does not understand
    by attempting to call the object's __str__ method. '''
    try:
        return str(obj)
    except Exception:
        return 'libhoney was unable to encode value'
