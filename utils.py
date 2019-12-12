from kodiswift import Plugin

from tridentstream_client import TridentstreamClient

__all__ = [
    'check_config',
    'get_client',
    'serialize_config',
    'plugin',
]

plugin = Plugin()

def check_config():
    return (plugin.get_setting('url', str) and
            plugin.get_setting('username', str) and
            plugin.get_setting('password', str))

def serialize_config():
    return (plugin.get_setting('url', str),
            plugin.get_setting('username', str),
            plugin.get_setting('password', str),
            plugin.get_setting('verify_ssl', bool))

def get_client():
    return TridentstreamClient(plugin.get_setting('url', str),
                               plugin.get_setting('username', str),
                               plugin.get_setting('password', str),
                               verify_ssl=plugin.get_setting('verify_ssl', bool))