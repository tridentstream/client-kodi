import logging

import requests

from .document import Document
from .resource import ResourceObject

logger = logging.getLogger(__name__)


class FailedToFetchDocumentException(Exception):
    pass


class JSONAPIClient(object):
    """
    Client used to fetch data, add authentication here.
    """

    def __init__(self, auth=None, headers=None, session=None):
        # type: (Optional[Tuple[str, str]], Optional[Mapping[str, str]], Optional[requests.Session]) -> None
        """
        Setup a new JSONAPI Client with proper authentication. A `requests.Session` is created.
        """
        if session:
            self.session = session
        else:
            self.session = requests.Session()

        if auth:
            self.session.auth = auth

        if headers:
            self.session.headers.update(headers)

        self.types = {}

    def get_document(self, url, query=None):
        return self.handle_document(self.session.get, url, query)

    def post_document(self, url, query=None, data=None):
        return self.handle_document(self.session.post, url, query, data)

    def handle_document(self, method, url, query=None, data=None):
        # type: (str) -> Document
        """
        Fetch and parse a Document from an URL.
        """

        logger.info('Fetching document at url:%s query:%r', url, query)
        try:
            if data:
                d = method(url, params=query, data=data)
            else:
                d = method(url, params=query)
        except requests.exceptions.RequestException:
            raise FailedToFetchDocumentException()

        document = Document(self)
        document.parse(d.json())
        return document

    def register_type(self, type_name, resource_cls):
        # type: (str, Type[ResourceObject]) -> None
        """
        Register a new type parser for resource objects in a document.
        """

        logger.info('Registering new type:%s', type_name)
        self.types[type_name] = resource_cls

    def register_types(self, type_name_resource_cls_mapping):
        for type_name, resource_cls in type_name_resource_cls_mapping.iteritems():
            self.register_type(type_name, resource_cls)

    def get_resource_object_type(self, type_name):
        return self.types.get(type_name, ResourceObject)