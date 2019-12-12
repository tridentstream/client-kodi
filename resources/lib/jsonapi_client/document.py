import logging

logger = logging.getLogger(__name__)


class Document(object):
    populated = False

    def __init__(self, json_client):
        self.json_client = json_client

        self.data = []
        self.included = []
        self.meta = {}
        self.links = {}
        self.relationships = {}

    def parse(self, obj):
        logger.info('Parsing object data')
        data = obj.get('data')
        if isinstance(data, dict):
            data = [data]

        if data:
            for item in data:
                self.data.append(self.create_resource_object(item))

        for item in obj.get('included', []):
            self.included.append(self.create_resource_object(item))

        self.meta.update(obj.get('meta', {}))
        self.links.update(obj.get('links', {}))

    def create_resource_object(self, item):
        resource_object_cls = self.json_client.get_resource_object_type(item['type'])

        key = (item['type'], item['id'])
        logger.info('Creating resource object with key:%r ro_class_obj%r', key, resource_object_cls)

        if key in self.relationships:
            obj = self.relationships[key]
        else:
            obj = self.relationships[key] = resource_object_cls(item['type'], item['id'], self.json_client)

        obj.parse(item, self)

        return obj

    def __iter__(self):
        return iter(self.data)

    #     self._object_registry = {}
    #
    # def get_or_create_resource_object(self, type_parsers, obj_data):
    #     id = obj_data['id']
    #     type = obj_data['type']
    #
    #     obj = self._object_registry.get((type, id))
    #     if not obj:
    #         cls = type_parsers.get(type, ResourceObject)
    #         self._object_registry[(type, id)] = obj = cls(type, id)
    #
    #     obj.parse(obj_data, self)
    #
    #     return obj
    #
    # @classmethod
    # def from_json(cls, json_client, type_parsers, json_obj, existing_resource_objects=None):
    #     obj = cls(json_client)
    #
    #     self.meta.update(json_obj.get('meta', {}))
    #     self.links.update(json_obj.get('links', {}))
    #
    #     data = json_obj.get(data)
    #     if isinstance(data, dict):
    #         data = [data]
    #
    #     if data:
    #         for obj_data in data:
    #             self.data.append(self.get_or_create_resource_object(type_parsers, obj_data))
    #
    #     for obj_data in json_obj.get('included', []):
    #         self.included.append(self.get_or_create_resource_object(type_parsers, obj_data))
    #
    #     return obj
    #
