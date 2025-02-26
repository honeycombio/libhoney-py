"""
Please perform an EXPORT of
CONFIG_KEY before starting
"""

import os
import unittest

import libhoney
from libhoney.marker import Marker

DATASET_NAME = 'honeycomb-python-example'



class TestCreateMarker(unittest.TestCase):
    """
    Response:

    resp_json={'id': 'x8zCKoa4sge', 'created_at': '2025-02-26T07:40:56Z', 'updated_at': '2025-02-26T07:40:56Z', 'start_time': 1740555656, 'message': 'backend deploy #123', 'type': 'deploy'}
/Users/necheng/Desktop/takehomes/libhoney-py/libhoney/client.py:237: ResourceWarning: unclosed <socket.socket fd=3, family=2, type=2, proto=0, laddr=('0.0.0.0', 0)>
  self.xmit = None
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.
----------------------------------------------------------------------
Ran 1 test in 0.255s

OK
    """
    def setUp(self):
        libhoney.init(writekey=os.getenv('CONFIG_KEY'), dataset=DATASET_NAME, debug=True)

    def tearDown(self):
        libhoney.close()

    def test_create_marker(self):
        marker = libhoney.new_marker(data={"message": "backend deploy #123", "type": "deploy"})
        resp = marker.send()
        self.assertEqual(resp.status_code, 201)
        resp_json = resp.json()
        self.assertEqual(resp_json['message'], "backend deploy #123")
        self.assertEqual(resp_json['type'], "deploy")



class TestDeleteMarker(unittest.TestCase):
    """
    Response:

    resp_json={'id': 'x8zCKoa4sge', 'created_at': '2025-02-26T07:40:56Z', 'updated_at': '2025-02-26T07:40:56Z', 'start_time': 1740555656, 'message': 'backend deploy #123', 'type': 'deploy'}
/Users/necheng/Desktop/takehomes/libhoney-py/libhoney/client.py:237: ResourceWarning: unclosed <socket.socket fd=3, family=2, type=2, proto=0, laddr=('0.0.0.0', 0)>
  self.xmit = None
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.
----------------------------------------------------------------------
Ran 1 test in 0.255s

OK
    """
    def setUp(self):
        libhoney.init(writekey=os.getenv('CONFIG_KEY'), dataset=DATASET_NAME, debug=True)

    def tearDown(self):
        libhoney.close()

    def test_delete_marker(self):
        marker = libhoney.new_marker(data={"message": "backend deploy #123", "type": "deploy"})
        resp_create = marker.send()
        self.assertEqual(resp_create.status_code, 201)
        resp_create_json = resp_create.json()

        resp_delete = marker.delete(resp_create_json['id'])
        self.assertEqual(resp_delete.status_code, 200)
        resp_delete_json = resp_delete.json()
        self.assertEqual(resp_delete_json['message'], "backend deploy #123")
        self.assertEqual(resp_delete_json['type'], "deploy")


