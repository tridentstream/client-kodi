from jsonapi_client import ResourceObject

from .player import TridentstreamPlayer

TYPE_MAPPING = {}

class ServiceResourceObject(ResourceObject):
    @property
    def can_access(self):
        for item in self.relationships['permission']['data']:
            if item['can_access']:
                return True
        return False


class ServiceSectionsResourceObject(ServiceResourceObject):
    pass

TYPE_MAPPING['service_sections'] = ServiceSectionsResourceObject


class StreamHttpResourceObject(ResourceObject):
    @property
    def media_url(self):
        return self.links['stream']

TYPE_MAPPING['stream_http'] = StreamHttpResourceObject


class DisplayMetadataResourceObject(ResourceObject):
    is_display_metadata = True

TYPE_MAPPING['metadata_imdb'] = DisplayMetadataResourceObject
TYPE_MAPPING['metadata_mal'] = DisplayMetadataResourceObject


class ServicePlayerResourceObject(ServiceResourceObject):
    def register_player(self, username, password, player_id, name, verify_ssl):
        return TridentstreamPlayer(self.links['self'], username, password, player_id, name, verify_ssl)

TYPE_MAPPING['service_player'] = ServicePlayerResourceObject
