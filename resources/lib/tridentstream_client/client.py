import requests

from urlparse import urljoin

from jsonapi_client import JSONAPIClient, FailedToFetchDocumentException

from .types import TYPE_MAPPING, ServicePlayerResourceObject


class TridentstreamClient(object):
    logged_in = False

    def __init__(self, url, username, password, verify_ssl=True):
        self.url = url
        self.username = username
        self.password = password

        self.session = requests.Session()
        self.session.verify = verify_ssl

        self.jsonapi_client = JSONAPIClient(auth=(username, password), session=self.session)
        self.jsonapi_client.register_types(TYPE_MAPPING)

    def get_endpoints(self):
        return self.get_document(urljoin(self.url, 'api/'))

    def get_document(self, url, query=None):
        return self.jsonapi_client.get_document(url, query)

    def stream_url(self, url):
        return self.jsonapi_client.post_document(url, data={'command': 'stream'})

    def register_player(self, player_id, name):
        for ro in self.get_endpoints():
            if isinstance(ro, ServicePlayerResourceObject):
                return ro.register_player(self.username, self.password, player_id, name, self.session.verify)
