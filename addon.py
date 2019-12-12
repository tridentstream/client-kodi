# -*- coding: utf-8 -*-
import json
import os
import sys

from datetime import datetime

library_path = os.path.join(os.path.dirname(__file__), 'resources', 'lib')
sys.path.append(library_path)

from kodiswift import xbmc

from utils import plugin, get_client, check_config, serialize_config


@plugin.route('/')
def index():
    tsc = get_client()

    sections = [s for s in tsc.get_endpoints() if s.type == 'service_sections']
    section_url = plugin.url_for('list_folder', url=json.dumps([s.links['self'] for s in sections]), titles=json.dumps([s['display_name'] for s in sections]))
    return plugin.redirect(section_url)


@plugin.route('/folder')
def list_folder():
    tsc = get_client()
    query = plugin.request.args.get('query')
    if query:
        query = json.loads(query[0])
    else:
        query = {}

    urls = json.loads(plugin.request.args.get('url')[0])
    if not isinstance(urls, list):
        urls = [urls]

    titles = plugin.request.args.get('titles')
    if titles:
        titles = json.loads(titles[0])
    else:
        titles = [''] * len(urls)

    query['limit'] = 1000

    items = []
    for parent_title, url in zip(titles, urls):
        while True:
            doc = tsc.get_document(url, query=query)

            for item in doc.data:
                item_query = {}
                if item.type == 'file':
                    url_name = 'play_file'
                    is_playable = True
                elif item.type == 'folder':
                    url_name = 'list_folder'
                    is_playable = False

                    metadata_filterinfo = item.relationships.get('metadata_filterinfo', {}).get('data')
                    if metadata_filterinfo:
                        metadata_filterinfo = metadata_filterinfo[0]
                        metadata_handlers = metadata_filterinfo.get('metadata_handlers')
                        if metadata_handlers:
                            item_query['include'] = ','.join(metadata_handlers)

                else:
                    continue

                item_info = {}

                if parent_title and len(urls) > 1:
                    name = '%s / %s' % (parent_title, item['name'])
                else:
                    name = item['name']

                list_item = {
                    'label': name,
                    'path': plugin.url_for(url_name, url=json.dumps(item.links['self']), query=json.dumps(item_query)),
                    'is_playable': is_playable,
                    'is_folder': not is_playable,
                    'info': item_info,
                    'info_type': 'video',
                }

                for relationship in item.relationships_flat:
                    if not getattr(relationship, 'is_display_metadata', False):
                        continue
                    metadata = relationship
                    if 'title' not in metadata:
                        continue

                    item_info['title'] = metadata['title']

                    if metadata.get('cover'):
                        list_item['icon'] = metadata['cover']

                    for key in ['plot', 'votes', 'rating', 'runtime']:
                        if key in metadata:
                            item_info[key] = metadata[key]

                    # TODO: add more metadata
                if item.get('datetime'):
                    item['date_added'] = item['datetime'].split('T')[0]

                if item.relationships.get('metadata_history'):
                    item_info['PlayCount'] = 1

                items.append(list_item)

            url = doc.links.get('next')
            if not url:
                break
            plugin.log.debug('Fetching next page')

    plugin.finish(items, sort_methods=['title', 'dateadded'])


@plugin.route('/file')
def play_file():
    tsc = get_client()
    url = json.loads(plugin.request.args.get('url')[0])
    doc = tsc.stream_url(url)

    for item in doc.data:
        if item.type == 'stream_http':
            return plugin.set_resolved_url({
                'label': item.id,
                'path': item.media_url,
            })


if __name__ == '__main__':
    if not check_config():
        plugin.open_settings()
    else:
        plugin.run()
