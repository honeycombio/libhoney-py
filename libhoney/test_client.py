'''Tests for libhoney/client.py'''

import unittest
import mock

import libhoney
import libhoney.client as client

def sample_dyn_fn():
    return "dyna", "magic"


class TestClient(unittest.TestCase):
    def setUp(self):
        libhoney.close()

        self.tx = mock.Mock()
        self.m_xmit = mock.patch('libhoney.client.Transmission')
        self.m_xmit.start().return_value = self.tx

    def tearDown(self):
        self.m_xmit.stop()

    def test_init(self):
        c = client.Client(writekey="foo", dataset="bar", api_host="blup",
                          sample_rate=2)
        self.assertEqual(c.writekey, "foo")
        self.assertEqual(c.dataset, "bar")
        self.assertEqual(c.api_host, "blup")
        self.assertEqual(c.sample_rate, 2)
        self.assertEqual(c.xmit, self.tx)

    def test_close(self):
        c = client.Client(writekey="foo", dataset="bar", api_host="blup",
                          sample_rate=2)
        c.close()
        self.tx.close.assert_called_with()
        self.assertEqual(c.xmit, None)

    def test_close_noop_if_not_init(self):
        """
        libhoney.close() should noop if never initialized
        """
        try:
            c = client.Client()
            c.close()
            # close again, should be a noop and not cause an exception
            c.close()
        except AttributeError:
            self.fail('libhoney threw an exception on '
                           'an uninitialized close.')

    def test_add_field(self):
        ed = {"whomp": True}
        with client.Client() as c:
            c.add_field("whomp", True)
            self.assertEqual(c.fields._data, ed)

    def test_add_dynamic_field(self):
        ed = set([sample_dyn_fn])
        with client.Client() as c:
            c.add_dynamic_field(sample_dyn_fn)
            self.assertEqual(c.fields._dyn_fields, ed)

    def test_add(self):
        ed = {"whomp": True}
        with client.Client() as c:
            c.add(ed)
            self.assertEqual(c.fields._data, ed)

    def test_new_event(self):
        with client.Client(writekey="client_key", dataset="client_dataset") as c:
            c.add_field("whomp", True)
            c.add_dynamic_field(sample_dyn_fn)

            ev = c.new_event({"field1": 1})
            ev.add_field("field2", 2)
            # ensure client config is passed through
            self.assertEqual(ev.client, c)
            self.assertEqual(ev.writekey, "client_key")
            self.assertEqual(ev.dataset, "client_dataset")
            # ensure client fields are passed on
            self.assertEqual(ev._fields._data, {"field1": 1, "field2": 2, "whomp": True, "sample_dyn_fn": ("dyna", "magic")})
            self.assertEqual(ev._fields._dyn_fields, set([sample_dyn_fn]))

    def test_new_builder(self):
        with client.Client(writekey="client_key", dataset="client_dataset") as c:
            c.add_field("whomp", True)
            c.add_dynamic_field(sample_dyn_fn)

            b = c.new_builder()
            # ensure client config is passed through
            self.assertEqual(b.client, c)
            self.assertEqual(b.writekey, "client_key")
            self.assertEqual(b.dataset, "client_dataset")
            b.add_field("builder_field", 1)

            ev = b.new_event()
            # ensure client config gets passed on
            self.assertEqual(ev.client, c)
            self.assertEqual(ev.writekey, "client_key")
            self.assertEqual(ev.dataset, "client_dataset")
            ev.add_field("event_field", 2)
            self.assertEqual(ev.client, c)
            # ensure client and builder fields are passed on
            self.assertEqual(ev._fields._data, {"builder_field": 1, "event_field": 2, "whomp": True, "sample_dyn_fn": ("dyna", "magic")})
            self.assertEqual(ev._fields._dyn_fields, set([sample_dyn_fn]))

    def test_send(self):
        ''' ensure that Event's `send()` calls the client `send()` method '''
        with client.Client(writekey="mykey", dataset="something") as c:
            # explicitly use a different object for Transmission than is
            # defined in setUp, to ensure we aren't using the global
            # xmit in libhoney
            c.xmit = mock.Mock()

            ev = c.new_event()
            ev.add_field("foo", "bar")
            ev.send()
            c.xmit.send.assert_called_with(ev)

    def test_send_global(self):
        ''' ensure that events sent using the global libhoney config work '''
        with client.Client(writekey="mykey", dataset="something") as c:
            # explicitly use a different object for Transmission than is
            # defined in setUp, to ensure we aren't using the global
            # xmit in libhoney
            c.xmit = mock.Mock()

            libhoney.init(writekey="someotherkey", dataset="somethingelse")
            ev = libhoney.Event()
            self.assertEqual(ev.writekey, "someotherkey")
            self.assertEqual(ev.dataset, "somethingelse")
            ev.add_field("global", "event")
            ev.send()
            # test our assumption about what's actually mocked
            self.assertEqual(libhoney.state.G_CLIENT.xmit, self.tx)
            # check that we used the global xmit
            self.tx.send.assert_called_with(ev)
            # check that the client xmit was not used
            self.assertFalse(c.xmit.send.called)

    def test_send_dropped_response(self):
        with mock.patch('libhoney.event._should_drop') as m_drop:
            m_drop.return_value = True

            with client.Client(writekey="mykey", dataset="something") as c:
                ev = c.new_event()
                ev.add_field("a", "b")
                ev.send()

                c.responses().put_nowait.assert_called_with({
                    "status_code": 0,
                    "duration": 0,
                    "metadata": ev.metadata,
                    "body": "",
                    "error": "event dropped due to sampling",
                })

    def test_xmit_override(self):
        '''verify that the client accepts an alternative Transmission'''
        mock_xmit = mock.Mock()
        with client.Client(transmission_impl=mock_xmit) as c:
            self.assertEqual(c.xmit, mock_xmit)

class TestClientFlush(unittest.TestCase):
    ''' separate test class because we don't want to mock transmission'''
    def test_flush(self):
        mock_xmit = mock.Mock(spec=libhoney.transmission.Transmission)
        with client.Client(transmission_impl=mock_xmit) as c:
            # start gets called when the class is initialized
            mock_xmit.start.assert_called_once_with()
            mock_xmit.reset_mock()
            c.flush()

            mock_xmit.close.assert_called_once_with()
            mock_xmit.start.assert_called_once_with()

        mock_xmit = mock.Mock(spec=libhoney.transmission.TornadoTransmission)
        with client.Client(transmission_impl=mock_xmit) as c:
            # start gets called when the class is initialized
            mock_xmit.start.assert_called_once_with()
            mock_xmit.reset_mock()
            c.flush()

            # we don't call close/start on TornadoTransmission because we can't
            # force a flush in an async environment.
            mock_xmit.close.assert_not_called()
            mock_xmit.start.assert_not_called()
