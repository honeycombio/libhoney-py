import json
import requests
from typing import Optional
from urllib.parse import urljoin

from libhoney import state
from libhoney.internal import json_default_handler


class Marker:
    '''A Marker is a designator at a certain timepoint that will be sent to Honeycomb.'''

    def __init__(self, data: Optional[dict] = None, client=None):
        if client is None:
            client = state.G_CLIENT

        self.writekey = client.writekey
        self.dataset = client.dataset
        self.api_host = client.api_host
        self.data = data if data else {}

    def add_field(self, entry: tuple[str, str | int | float]):
        key, val = entry
        self.data[key] = val

    def fields(self):
        return self.data

    def send(self):
        """sending data to Honeycomb"""
        url = urljoin(urljoin(self.api_host, "/1/markers/"),
                      self.dataset)
        data = json.dumps(self.fields(), default=json_default_handler)

        resp = requests.post(url,
                             headers={"X-Honeycomb-Team": self.writekey,
                                      "Content-Type": "application/json"},
                             data=data,
                             timeout=10.0,
                             )

        resp.raise_for_status()
        print('Request successful!\n')
        resp_json = resp.json()
        print(f'{resp_json=}')
        return resp

    def delete(self, marker_id: str):
        url = urljoin(self.api_host, f"/1/markers/{self.dataset}/{marker_id}")
        print(url)
        resp = requests.delete(url,
                             headers={"X-Honeycomb-Team": self.writekey,
                                      "Content-Type": "application/json"},
                             timeout=10.0,
                             )

        resp.raise_for_status()
        print('Request successful!\n')
        resp_json = resp.json()
        print(f'{resp_json=}')
        return resp

