'''Tests for libhoney/__init__.py'''

import __init__ as libhoney

import datetime
import unittest
import mock


def sample_dyn_fn():
    return "dyna", "magic"


class FakeTransmitter():
    def __init__(self, id):
        self.id = id

    def get_response_queue(self):
        return None


class TestGlobalScope(unittest.TestCase):
    def setUp(self):
        libhoney._fields = libhoney.FieldHolder()

    def test_init(self):
        ft = FakeTransmitter(3)
        real_transmission = libhoney.transmission.Transmission
        libhoney.transmission.Transmission = mock.MagicMock(return_value=ft)
        libhoney.init(writekey="wk", dataset="ds", sample_rate=3,
                      api_host="uuu", max_concurrent_batches=5,
                      block_on_response=True)
        self.assertEqual(libhoney.g_writekey, "wk")
        self.assertEqual(libhoney.g_dataset, "ds")
        self.assertEqual(libhoney.g_api_host, "uuu")
        self.assertEqual(libhoney.g_sample_rate, 3)
        self.assertEqual(libhoney._xmit, ft)
        self.assertEqual(libhoney.g_responses, None)
        libhoney.transmission.Transmission.assert_called_with(
            5, False, True)
        libhoney.transmission.Transmission = real_transmission

    def test_close(self):
        mock_xmit = mock.MagicMock()
        libhoney._xmit = mock_xmit
        libhoney.close()
        mock_xmit.close.assert_called_with()
        self.assertEqual(libhoney._xmit, None)

    def test_add_field(self):
        ed = {"whomp": True}
        libhoney.add_field("whomp", True)
        self.assertEqual(libhoney._fields._data, ed)

    def test_add_dynamic_field(self):
        ed = set([sample_dyn_fn])
        libhoney.add_dynamic_field(sample_dyn_fn)
        self.assertEqual(libhoney._fields._dyn_fields, ed)

    def test_add(self):
        ed = {"whomp": True}
        libhoney.add(ed)
        self.assertEqual(libhoney._fields._data, ed)


class TestFieldHolder(unittest.TestCase):
    def setUp(self):
        libhoney._fields = libhoney.FieldHolder()

    def test_add_field(self):
        expected_data = {}
        self.assertEqual(libhoney._fields._data, expected_data)
        self.assertTrue(libhoney._fields.is_empty())
        libhoney.add_field("foo", 4)
        expected_data["foo"] = 4
        self.assertEqual(libhoney._fields._data, expected_data)
        self.assertFalse(libhoney._fields.is_empty())
        libhoney.add_field("bar", "baz")
        expected_data["bar"] = "baz"
        self.assertEqual(libhoney._fields._data, expected_data)
        libhoney.add_field("foo", 6)
        expected_data["foo"] = 6
        self.assertEqual(libhoney._fields._data, expected_data)

    def test_add_dynamic_field(self):
        expected_dyn_fns = set()
        self.assertEqual(libhoney._fields._dyn_fields, expected_dyn_fns)
        libhoney.add_dynamic_field(sample_dyn_fn)
        expected_dyn_fns.add(sample_dyn_fn)
        self.assertEqual(libhoney._fields._dyn_fields, expected_dyn_fns)
        # adding a second time should still only have one element
        libhoney.add_dynamic_field(sample_dyn_fn)
        self.assertEqual(libhoney._fields._dyn_fields, expected_dyn_fns)
        with self.assertRaises(TypeError):
            libhoney.add_dynamic_field("foo")



class TestBuilder(unittest.TestCase):
    def setUp(self):
        libhoney._fields = libhoney.FieldHolder()

    def test_new_builder(self):
        # new builder, no arguments
        b = libhoney.Builder()
        self.assertEqual(b._fields._data, {})
        self.assertEqual(b._fields._dyn_fields, set())
        # new builder, passed in data and dynfields
        expected_data = {"aa": 1}
        expected_dyn_fns = set([sample_dyn_fn])
        b = libhoney.Builder(expected_data, expected_dyn_fns)
        self.assertEqual(b._fields._data, expected_data)
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)
        # new builder, inherited data and dyn_fields
        libhoney._fields._data = expected_data
        libhoney._fields._dyn_fields = expected_dyn_fns
        b = libhoney.Builder()
        self.assertEqual(b._fields._data, expected_data)
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)
        # new builder, merge inherited data and dyn_fields and arguments

        def sample_dyn_fn2():
            return 5
        expected_data = {"aa": 1, "b": 2}
        expected_dyn_fns = set([sample_dyn_fn, sample_dyn_fn2])
        b = libhoney.Builder({"b": 2}, [sample_dyn_fn2])
        self.assertEqual(b._fields._data, expected_data)
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)

    def test_add_field(self):
        b = libhoney.Builder()
        expected_data = {}
        self.assertEqual(b._fields._data, expected_data)
        b.add_field("foo", 4)
        expected_data["foo"] = 4
        self.assertEqual(b._fields._data, expected_data)
        b.add_field("bar", "baz")
        expected_data["bar"] = "baz"
        self.assertEqual(b._fields._data, expected_data)
        b.add_field("foo", 6)
        expected_data["foo"] = 6
        self.assertEqual(b._fields._data, expected_data)

    def test_add_dynamic_field(self):
        b = libhoney.Builder()
        expected_dyn_fns = set()
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)
        b.add_dynamic_field(sample_dyn_fn)
        expected_dyn_fns.add(sample_dyn_fn)
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)
        with self.assertRaises(TypeError):
            b.add_dynamic_field("foo")

    def test_add(self):
        b = libhoney.Builder()
        expected_data = {"a": 1, "b": 3}
        b.add(expected_data)
        self.assertEqual(b._fields._data, expected_data)
        expected_data.update({"c": 3, "d": 4})
        b.add({"c": 3, "d": 4})
        self.assertEqual(b._fields._data, expected_data)

    def test_new_event(self):
        b = libhoney.Builder()
        b.sample_rate = 5
        expected_data = {"a": 1, "b": 3}
        b.add(expected_data)
        ev = b.new_event()
        self.assertEqual(b._fields, ev._fields)
        self.assertEqual(ev.sample_rate, 5)
        ev.add_field("3", "c")
        self.assertNotEqual(b._fields, ev._fields)
        # move to event testing when written
        self.assertEqual(str(ev), '''{"a": 1, "3": "c", "b": 3}''')

    def test_clone_builder(self):
        b = libhoney.Builder()
        b.dataset = "newds"
        b.add_field("e", 9)
        b.add_dynamic_field(sample_dyn_fn)
        c = b.clone()
        self.assertEqual(b._fields, c._fields)
        c.add_field("f", 10)
        b.add_field("g", 11)
        self.assertEqual(b._fields._data, {"e": 9, "g": 11})
        self.assertEqual(c._fields._data, {"e": 9, "f": 10})
        self.assertEqual(c.dataset, "newds")


class TestEvent(unittest.TestCase):
    def setUp(self):
        libhoney._fields = libhoney.FieldHolder()

    def test_timer(self):
        class fakeDate:
            def setNow(self, time):
                self.time = time
            def now(self):
                return self.time
            def utcnow(self):
                return self.time
        fakeStart = datetime.datetime(2016, 1, 2, 3, 4, 5, 6)
        fakeEnd = fakeStart + datetime.timedelta(milliseconds=5)
        fd = fakeDate()
        fd.setNow(fakeStart)
        real_datetime = datetime.datetime
        libhoney.datetime.datetime = fd
        ev = libhoney.Event()
        with ev.timer("howlong"):
            fd.setNow(fakeEnd)
        self.assertEqual(ev._fields._data, {"howlong": 5})
        self.assertEqual(ev.created_at, fakeStart)
        libhoney.datetime.datetime = real_datetime

    def test_send(self):
        libhoney._xmit = mock.MagicMock()

        ev = libhoney.Event()
        with self.assertRaises(libhoney.SendError) as c1:
            ev.send()
        self.assertTrue("No metrics added to event. Won't send empty event." in c1.exception)
        ev = libhoney.Event()
        ev.add_field("f", "g")
        with self.assertRaises(libhoney.SendError) as c2:
            ev.send()
        self.assertTrue("No APIHost for Honeycomb. Can't send to the Great Unknown." in c2.exception)
        ev.api_host = "myhost"
        with self.assertRaises(libhoney.SendError) as c2:
            ev.send()
        self.assertTrue("No WriteKey specified. Can't send event." in c2.exception)
        ev.writekey = "letmewrite"
        with self.assertRaises(libhoney.SendError) as c2:
            ev.send()
        self.assertTrue("No Dataset for Honeycomb. Can't send datasetless." in c2.exception)
        ev.dataset = "storeme"
        ev.send()
        libhoney._xmit.send.assert_called_with(ev)

    def test_send_sampling(self):
        libhoney._xmit = mock.MagicMock()
        libhoney._should_drop = mock.MagicMock(return_value=True)

        # test that send() drops when should_drop is true
        ev = libhoney.Event()
        ev.send()
        libhoney._xmit.send.assert_not_called()
        libhoney._should_drop.assert_called_with(1)
        ev = libhoney.Event()
        ev.sample_rate = 5
        ev.send()
        libhoney._xmit.send.assert_not_called()
        libhoney._should_drop.assert_called_with(5)

        # and actually sends them along when should_drop is false
        libhoney._should_drop = mock.MagicMock(return_value=False)
        ev = libhoney.Event()
        ev.add_field("f", "g")
        ev.api_host = "myhost"
        ev.writekey = "letmewrite"
        ev.dataset = "storeme"
        ev.send()
        libhoney._xmit.send.assert_called_with(ev)
        libhoney._should_drop.assert_called_with(1)
        ev.sample_rate = 5
        ev.send()
        libhoney._xmit.send.assert_called_with(ev)
        libhoney._should_drop.assert_called_with(5)

        # test that send_presampled() does not drop
        libhoney._should_drop.reset_mock()
        ev.send_presampled()
        libhoney._xmit.send.assert_called_with(ev)
        libhoney._should_drop.assert_not_called()
        ev.sample_rate = 5
        ev.send_presampled()
        libhoney._xmit.send.assert_called_with(ev)
        libhoney._should_drop.assert_not_called()
