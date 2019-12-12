import copy
import json
import logging
import time
import threading
import uuid
import os
import sys

from functools import partial

library_path = os.path.join(os.path.dirname(__file__), 'resources', 'lib')
sys.path.append(library_path)

from kodiswift import xbmc, xbmcaddon

from utils import plugin, get_client, check_config, serialize_config
from tridentstream_client import FailedToFetchDocumentException

logging.basicConfig(level=logging.DEBUG)


def timestamp2seconds(timestamp):
    return (timestamp['hours'] * 60 + timestamp['minutes']) * 60 + timestamp['seconds'] + timestamp['milliseconds'] / 1000.0


def seconds2timestamp(seconds):
    return {
        'hours': int(seconds / 60 / 60),
        'minutes': int((seconds % 3600) / 60),
        'seconds': int((seconds % 60)),
        'milliseconds': int((seconds % 1)*1000),
    }


def executeJSONRPC(method, **kwargs):
    payload = json.dumps({
        'jsonrpc': '2.0',
        'method': method,
        'id': 1,
        "params": kwargs,
    })

    data = xbmc.executeJSONRPC(payload)

    return json.loads(data).get('result', None)


def get_player():
    players = executeJSONRPC('Player.GetActivePlayers')
    if not players:
        return None

    return players[0]['playerid']

class TidalTracker(object):
    viewstate = None
    last_state = None

    tridentstream_player = None
    tracking_player = None

    _die = False

    def __init__(self, tracking_player):
        self.update_lock = threading.Lock()
        self.update_schedule = []

        self.tracking_player = tracking_player

        def on_update(link_viewstate):
            self.schedule_update(delay=0, link_viewstate=link_viewstate)
        tracking_player.on_update = on_update

        self.run_update_loop()

    def die(self):
        plugin.log.info('Plugin dying!')
        self.disconnect_player()
        self._die = True

    def connect_player(self, tridentstream_player):
        plugin.log.debug('Connecting player')
        self.last_state = {'state': None}

        self.tridentstream_player = tridentstream_player

        tridentstream_player.register_command('play', self.command_play)
        tridentstream_player.register_command('next', self.command_next)
        tridentstream_player.register_command('previous', self.command_previous)
        tridentstream_player.register_command('request_state', self.request_state)

        tridentstream_player.set_option('speed', [0, 1, 2, 4, 8, -1, -2, -4, -8])

        tridentstream_player.connect()

        self.schedule_update(delay=3)

    def disconnect_player(self):
        if self.tridentstream_player:
            self.tridentstream_player.close()
        self.tridentstream_player = None

    @property
    def usable(self):
        return self.tridentstream_player is not None

    def check_for_state_update(self, link_viewstate=False):
        if not self.usable:
            return

        try:
            current_state = self.tracking_player.get_current_state()
        except:
            plugin.log.exception('Failed to get state from player')
        else:
            values = copy.copy(current_state)
            state = values.pop('state')

            if link_viewstate:
                if state == 'playing' and self.viewstate:
                    plugin.log.info('Set name to %s for viewstate %s' % (values['name'], self.viewstate['id']))
                    self.request_state('playing', self.viewstate)

                if state == 'stopped' and self.viewstate:
                    plugin.log.info('Clearing viewstate %s' % (self.viewstate['id']))
                    self.viewstate = None

            if state == self.last_state['state'] and self.tridentstream_player.sent_full_state:
                for k, v in values.items():
                    if self.last_state[k] == v:
                        del values[k]

            if values or state != self.last_state['state']:
                viewstate_id = self.viewstate and self.viewstate.get('id') or None
                if self.tridentstream_player.logged_in:
                    self.tridentstream_player.sent_full_state = True
                    self.tridentstream_player.send_command('state', state, values, viewstate_id)

            self.last_state = current_state

    def request_state(self, state, values):
        plugin.log.debug('Requesting state %s with values %r' % (state, values))
        current_state = self.tracking_player.get_current_state()
        if state == 'stopped':
            executeJSONRPC('Player.Stop', playerid=get_player())
        elif state == 'playing':
            for k, v in values.iteritems():
                if current_state.get(k, None) == v:
                    continue

                if get_player() is None:
                    continue

                if k == 'current_time': # seek
                    executeJSONRPC('Player.Seek', playerid=get_player(), value=seconds2timestamp(v))
                elif k == 'current_audiostream': # change audio stream
                    executeJSONRPC('Player.SetAudioStream', playerid=get_player(), stream=v)
                elif k == 'current_subtitle': # change subtitle
                    if v is None:
                        executeJSONRPC('Player.SetSubtitle', playerid=get_player(), subtitle='off')
                    else:
                        executeJSONRPC('Player.SetSubtitle', playerid=get_player(), subtitle=v, enable=True)
                elif k == 'speed': # change speed
                    executeJSONRPC('Player.SetSpeed', playerid=get_player(), speed=v)
                else:
                    plugin.log.warning('Unknown command: %r - %r' % (k, v))

        self.schedule_update(delay=0)
        self.schedule_update(delay=3)

    def command_play(self, streamresult, viewstate):
        plugin.log.info('Got a request to play %r - Current viewstate is %s' % (streamresult, viewstate))

        self.viewstate = viewstate
        self.streamresult = streamresult

        self.tracking_player.play(streamresult['url'])
        self.schedule_update(delay=0)
        self.schedule_update(delay=3)

    def command_next(self):
        executeJSONRPC('Player.GoTo', to='next', playerid=get_player())
        self.schedule_update(delay=2)

    def command_previous(self):
        executeJSONRPC('Player.GoTo', to='previous', playerid=get_player())
        self.schedule_update(delay=2)

    def schedule_update(self, delay=10, link_viewstate=False):
        plugin.log.debug('Scheduling update in %i with link_viewstate %r' % (delay, link_viewstate, ))
        with self.update_lock:
            self.update_schedule.append((time.time() + delay, link_viewstate))
            self.update_schedule = sorted(self.update_schedule)

    def run_update_loop(self):
        plugin.log.info('Running update loop')

        def loop():
            plugin.log.info('Threaded loop started')
            while not self._die:
                if not self.update_schedule:
                    self.schedule_update()

                do_update = False
                link_viewstate = False
                with self.update_lock:
                    if self.update_schedule and self.update_schedule[0][0] <= time.time():
                        link_viewstate = self.update_schedule.pop(0)[1]
                        do_update = True

                if do_update:
                    self.check_for_state_update(link_viewstate=link_viewstate)

                time.sleep(0.5)
            plugin.log.info('Threaded loop ended')

        thread = threading.Thread(target=loop)
        thread.setDaemon(True)
        thread.start()


class TrackingPlayer(xbmc.Player):
    on_update = None
    def __init__(self):
        self.onPlayBackPaused = self.inform_about_potential_update
        self.onPlayBackResumed = self.inform_about_potential_update
        self.onPlayBackSeek = self.inform_about_potential_update
        self.onPlayBackSeekChapter = self.inform_about_potential_update
        self.onPlayBackSpeedChanged = self.inform_about_potential_update

        self.onPlayBackStarted = self.inform_about_potential_new_update

        self.onPlayBackEnded = self.inform_about_potential_new_update
        self.onPlayBackStopped = self.inform_about_potential_new_update

        xbmc.Player.__init__(self)

    def get_current_state(self):
        title = executeJSONRPC('Player.GetItem', properties=['title'], playerid=get_player())
        if title is None:
            return {'state': 'stopped'}

        retval = {'state': 'playing'}
        title = title['item']['title']

        retval['name'] = self.getPlayingFile()

        chapters = executeJSONRPC('XBMC.GetInfoLabels', labels=['Player.ChapterCount'])['Player.ChapterCount']
        current_chapter = executeJSONRPC('XBMC.GetInfoLabels', labels=['Player.Chapter'])['Player.Chapter']
        retval['chapters'] = chapters and int(chapters) or 0
        retval['current_chapter'] = current_chapter and int(current_chapter) or 0

        if not title and self.isPlayingVideo():
           title = executeJSONRPC('XBMC.GetInfoLabels', labels=['VideoPlayer.Title'])['VideoPlayer.Title']

        retval['title'] = title

        current_status = executeJSONRPC('Player.GetProperties', properties=['audiostreams', 'subtitles', 'currentaudiostream', 'currentsubtitle', 'time', 'totaltime', 'type', 'speed'], playerid=get_player())

        retval['speed'] = current_status['speed']
        retval['length'] = timestamp2seconds(current_status['totaltime'])
        retval['current_time'] = timestamp2seconds(current_status['time'])

        retval['audiostreams'] = [(audiostream['index'], audiostream['name'] or audiostream['language']) for audiostream in current_status['audiostreams']]
        current_audiostream = None
        if current_status['currentaudiostream']:
            current_audiostream = current_status['currentaudiostream']['index']
        retval['current_audiostream'] = current_audiostream

        retval['subtitles'] = [(subtitle['index'], subtitle['name'] or subtitle['language']) for subtitle in current_status['subtitles']]
        current_subtitle = None
        if current_status['currentsubtitle']:
            current_subtitle = current_status['currentsubtitle']['index']
        retval['current_subtitle'] = current_subtitle

        return retval

    def inform_about_potential_update(self, *args):
        if self.on_update:
             self.on_update(False)

    def inform_about_potential_new_update(self, *args):
        if self.on_update:
             self.on_update(True)


if __name__ == '__main__':
    if not plugin.get_setting('player_id', str):
        plugin.set_setting('player_id', str(uuid.uuid4()))

    monitor = xbmc.Monitor()

    tp = TrackingPlayer()
    tt = TidalTracker(tp)
    last_config = None
    no_player_found = None

    while True:
        if check_config():
            if tt.usable and serialize_config() != last_config:
                plugin.log.info('Config was changed, lets kill old websocket connection')
                tt.disconnect_player()
                no_player_found = None
                time.sleep(3)

            if not tt.usable and (no_player_found is None or no_player_found < time.time()):
                plugin.log.info('Seems like websocket is not running, lets try to rectify that')
                tsc = get_client()

                player_id = plugin.get_setting('player_id')
                name = xbmc.getInfoLabel('System.FriendlyName')

                try:
                    player = tsc.register_player(player_id, name)
                except FailedToFetchDocumentException:
                    player = None

                if not player:
                    plugin.log.warning('No player found, lets try later')
                    no_player_found = time.time() + (2 * 60)
                else:
                    no_player_found = None
                    tt.connect_player(player)
                    last_config = serialize_config()

        try:
            if monitor.waitForAbort(1):
                plugin.log.info('Plugin told to stop!')
                tt.die()
                break
        except:
            plugin.log.info('We got some exception')
            tt.die()
            break
