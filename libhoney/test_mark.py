from libhoney.marker import Marker, MarkerFieldsInvalidException

def test_create_invalid_mark():
    try:
        Marker({'invalid_field': 'invalid'})
    except MarkerFieldsInvalidException:
        assert True
    else:
        assert False