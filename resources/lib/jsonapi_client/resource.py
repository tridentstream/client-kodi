import logging

logger = logging.getLogger(__name__)


class ResourceObject(dict):
    populated = False

    def __init__(self, type, id, json_client):
        self.json_client = json_client

        self.type = type
        self.id = id
        self.relationships = {}
        self.relationships_flat = []
        self.links = {}
        self.meta = {}

        self.document = None

    def parse(self, obj_data, document):
        logger.debug('Parsing resorce object data')
        attributes = obj_data.get('attributes', {})
        if attributes:
            self.populated = True
            self.update(attributes)

        for relationship_name, relationship in obj_data.get('relationships', {}).iteritems():
            self.create_relationship(relationship_name, relationship, document)

        self.links.update(obj_data.get('links', {}))
        self.meta.update(obj_data.get('meta', {}))

    def create_relationship(self, name, relationship, document):
        logger.debug('Creating relationships from name:%s', name)
        self.relationships[name] = {}

        data = relationship.get('data')
        if data:
            if isinstance(data, dict):
                data = [data]

            self.relationships[name]['data'] = []
            for item in data:
                ro = document.create_resource_object(item)
                self.relationships[name]['data'].append(ro)
                self.relationships_flat.append(ro)

        self.relationships[name]['links'] = relationship.get('links', {})

    def get_document(self, query=None, keep_document=False):
        url = self.links['self']

        if not query and keep_document and self.document:
            return self.document

        document = self.json_client.get_document(url, query)
        if not query and keep_document:
            self.document = document

        return document

    def __repr__(self):
        return "<%s(type=%r, id=%r)>" % (self.__class__.__name__, self.type, self.id, )
