'''Tests for libhoney/__init__.py'''

import datetime
import json
import mock
import unittest

import libhoney


def sample_dyn_fn():
    return "dyna", "magic"


class FakeTransmitter():
    def __init__(self, id):
        self.id = id

    def start(self):
        pass

    def close(self):
        pass

    def get_response_queue(self):
        return None


class TestGlobalScope(unittest.TestCase):
    def setUp(self):
        # reset global state with each test
        libhoney.close()
        self.mock_xmit = mock.Mock(return_value=mock.Mock())

    def test_init(self):
        ft = FakeTransmitter(3)
        with mock.patch('libhoney.client.Transmission') as m_xmit:
            m_xmit.return_value = ft
            libhoney.init(writekey="wk", dataset="ds", sample_rate=3,
                          api_host="uuu", max_concurrent_batches=5,
                          block_on_response=True)
            self.assertEqual(libhoney.state.G_CLIENT.writekey, "wk")
            self.assertEqual(libhoney.state.G_CLIENT.dataset, "ds")
            self.assertEqual(libhoney.state.G_CLIENT.api_host, "uuu")
            self.assertEqual(libhoney.state.G_CLIENT.sample_rate, 3)
            self.assertEqual(libhoney.state.G_CLIENT.xmit, ft)
            self.assertEqual(libhoney.state.G_CLIENT._responses, None)
            m_xmit.assert_called_with(
                block_on_response=True, block_on_send=False,
                max_concurrent_batches=5, user_agent_addition='',
                debug=False,
            )

    def test_close(self):
        mock_client = mock.Mock()
        libhoney.state.G_CLIENT = mock_client
        libhoney.close()
        mock_client.close.assert_called_with()
        self.assertEqual(libhoney.state.G_CLIENT, None)

    def test_close_noop_if_not_init(self):
        """
        libhoney.close() should noop if never initialized
        """
        try:
            libhoney.close()
        except AttributeError:
            self.fail('libhoney threw an exception on '
                      'an uninitialized close.')

    def test_add_field(self):
        libhoney.init()
        ed = {"whomp": True}
        libhoney.add_field("whomp", True)
        self.assertEqual(libhoney.state.G_CLIENT.fields._data, ed)

    def test_add_dynamic_field(self):
        libhoney.init()
        ed = set([sample_dyn_fn])
        libhoney.add_dynamic_field(sample_dyn_fn)
        self.assertEqual(libhoney.state.G_CLIENT.fields._dyn_fields, ed)

    def test_add(self):
        libhoney.init()
        ed = {"whomp": True}
        libhoney.add(ed)
        self.assertEqual(libhoney.state.G_CLIENT.fields._data, ed)


class TestFieldHolder(unittest.TestCase):
    def setUp(self):
        # reset global state with each test
        libhoney.close()

    def test_add_field(self):
        libhoney.init()
        expected_data = {}
        self.assertEqual(libhoney.state.G_CLIENT.fields._data, expected_data)
        self.assertTrue(libhoney.state.G_CLIENT.fields.is_empty())
        libhoney.add_field("foo", 4)
        expected_data["foo"] = 4
        self.assertEqual(libhoney.state.G_CLIENT.fields._data, expected_data)
        self.assertFalse(libhoney.state.G_CLIENT.fields.is_empty())
        libhoney.add_field("bar", "baz")
        expected_data["bar"] = "baz"
        self.assertEqual(libhoney.state.G_CLIENT.fields._data, expected_data)
        libhoney.add_field("foo", 6)
        expected_data["foo"] = 6
        self.assertEqual(libhoney.state.G_CLIENT.fields._data, expected_data)

    def test_add_dynamic_field(self):
        libhoney.init()
        expected_dyn_fns = set()
        self.assertEqual(
            libhoney.state.G_CLIENT.fields._dyn_fields, expected_dyn_fns)
        libhoney.add_dynamic_field(sample_dyn_fn)
        expected_dyn_fns.add(sample_dyn_fn)
        self.assertEqual(
            libhoney.state.G_CLIENT.fields._dyn_fields, expected_dyn_fns)
        # adding a second time should still only have one element
        libhoney.add_dynamic_field(sample_dyn_fn)
        self.assertEqual(
            libhoney.state.G_CLIENT.fields._dyn_fields, expected_dyn_fns)
        with self.assertRaises(TypeError):
            libhoney.add_dynamic_field("foo")


class TestBuilder(unittest.TestCase):
    def setUp(self):
        # reset global state with each test
        libhoney.close()

    def test_new_builder(self):
        libhoney.init()
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
        libhoney.state.G_CLIENT.fields._data = expected_data
        libhoney.state.G_CLIENT.fields._dyn_fields = expected_dyn_fns
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
        libhoney.init()
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
        libhoney.init()
        b = libhoney.Builder()
        expected_dyn_fns = set()
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)
        b.add_dynamic_field(sample_dyn_fn)
        expected_dyn_fns.add(sample_dyn_fn)
        self.assertEqual(b._fields._dyn_fields, expected_dyn_fns)
        with self.assertRaises(TypeError):
            b.add_dynamic_field("foo")

    def test_add(self):
        libhoney.init()
        b = libhoney.Builder()
        expected_data = {"a": 1, "b": 3}
        b.add(expected_data)
        self.assertEqual(b._fields._data, expected_data)
        expected_data.update({"c": 3, "d": 4})
        b.add({"c": 3, "d": 4})
        self.assertEqual(b._fields._data, expected_data)

    def test_new_event(self):
        libhoney.init()
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
        self.assertEqual(json.loads(str(ev)), {"a": 1, "3": "c", "b": 3})

    def test_clone_builder(self):
        libhoney.init()

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
        # reset global state with each test
        libhoney.close()

    def test_timer(self):
        libhoney.init()

        class fakeDate:
            def setNow(self, time):
                self.time = time

            def now(self):
                return self.time

            def utcnow(self):
                return self.time

        with mock.patch('libhoney.event.datetime') as m_datetime:
            fakeStart = datetime.datetime(2016, 1, 2, 3, 4, 5, 6)
            fakeEnd = fakeStart + datetime.timedelta(milliseconds=5)
            fd = fakeDate()
            fd.setNow(fakeStart)
            m_datetime.datetime = fd
            ev = libhoney.Event()
            with ev.timer("howlong"):
                fd.setNow(fakeEnd)
            self.assertEqual(ev._fields._data, {"howlong": 5})
            self.assertEqual(ev.created_at, fakeStart)

    def test_str(self):
        libhoney.init()
        ev = libhoney.Event()
        ev.add_field("obj", {"a": 1})
        ev.add_field("string", "a:1")
        ev.add_field("number", 5)
        ev.add_field("boolean", True)
        ev.add_field("null", None)

        serialized = str(ev)
        self.assertTrue('"obj": {"a": 1}' in serialized)
        self.assertTrue('"string": "a:1"' in serialized)
        self.assertTrue('"number": 5' in serialized)
        self.assertTrue('"boolean": true' in serialized)
        self.assertTrue('"null": null' in serialized)

    def test_send(self):
        with mock.patch('libhoney.client.Transmission') as m_xmit:
            libhoney.init()
            ev = libhoney.Event()
            # override inherited api_host from client
            ev.api_host = ""
            ev.add_field("f", "g")
            ev.api_host = "myhost"
            ev.writekey = "letmewrite"
            ev.dataset = "storeme"
            ev.send()
            m_xmit.return_value.send.assert_called_with(ev)

    def test_send_sampling(self):
        with mock.patch('libhoney.client.Transmission') as m_xmit,\
                mock.patch('libhoney.event._should_drop') as m_sd:
            m_sd.return_value = True
            libhoney.init(writekey="wk", dataset="ds")

            # test that send() drops when should_drop is true
            ev = libhoney.Event()
            ev.add_field("foo", 1)
            ev.send()
            m_xmit.return_value.send.assert_not_called()
            m_sd.assert_called_with(1)
            ev = libhoney.Event()
            ev.add_field("foo", 1)
            ev.sample_rate = 5
            ev.send()
            m_xmit.return_value.send.assert_not_called()
            m_sd.assert_called_with(5)

            # and actually sends them along when should_drop is false
            m_sd.reset_mock()
            m_xmit.reset_mock()
            m_sd.return_value = False

            ev = libhoney.Event()
            ev.add_field("f", "g")
            ev.api_host = "myhost"
            ev.writekey = "letmewrite"
            ev.dataset = "storeme"
            ev.send()
            m_xmit.return_value.send.assert_called_with(ev)
            m_sd.assert_called_with(1)
            ev.sample_rate = 5
            ev.send()
            m_xmit.return_value.send.assert_called_with(ev)
            m_sd.assert_called_with(5)

            # test that send_presampled() does not drop
            m_sd.reset_mock()
            m_xmit.reset_mock()
            ev.send_presampled()
            m_xmit.return_value.send.assert_called_with(ev)
            m_sd.assert_not_called()

            m_sd.reset_mock()
            m_xmit.reset_mock()
            ev.sample_rate = 5
            ev.send_presampled()
            m_xmit.return_value.send.assert_called_with(ev)
            m_sd.assert_not_called()
