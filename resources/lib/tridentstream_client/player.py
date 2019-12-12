import base64
import logging
import ssl
import time
import threading

import websocket

from jsonrpclib.jsonrpc import dumps, loads, random_id

logger = logging.getLogger(__name__)


class TridentstreamPlayer(object):
    logged_in = False
    sent_full_state = False
    die = False
    _ws = None

    def __init__(self, url, username, password, player_id, name, verify_ssl):
        if url.startswith('http'):
            url = 'ws%s' % (url[4:], )
        self.url = url

        self.username = username
        self.password = password
        self.player_id = player_id
        self.name = name
        self.commands = []
        self.method_register = {}
        self.options = {}
        self._ws_lock = threading.Lock()

        if verify_ssl:
            self.ssh_opts = {}
        else:
            self.ssh_opts = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}

    def register_command(self, name, fn):
        logger.debug('Registering command %s' % (name, ))
        self.commands.append(name)
        self.method_register[name] = fn

    def set_option(self, key, value):
        logger.debug('Setting option %s to %r' % (key, value, ))
        self.options[key] = value

    def connect(self):
        logger.info('Trying to login as %s at %s' % (self.username, self.url))
        if self._ws:
            self.disconnect()

        with self._ws_lock:
            self._ws = websocket.WebSocketApp(
                self.url,
                header=['Authorization: Basic %s' % (base64.b64encode('%s:%s' % (self.username, self.password)), )],

                on_message=self._on_message,
                # on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open,
            )

        thread = threading.Thread(target=self._ws.run_forever, kwargs={'sslopt': self.ssh_opts})
        thread.setDaemon(True)
        thread.start()

    def disconnect(self):
        logger.info('Disconnecting player.')
        pass

    def _on_message(self, ws, payload):
        logger.debug('Got message: %r' % (payload, ))

        msg = loads(payload)
        method = msg.get('method')
        logger.debug('Got message: %r' % (msg, ))

        if method:
            f = self.method_register.get(method)
            if f:
                logger.info('Calling %s with %r' % (method, msg['params']))
                f(*msg['params'])
            else:
                logger.warning('Unknown method %s' % method)
        else:
            logger.info('Not sure what to do about: %r' % (msg, ))

    def _on_close(self, ws): # TODO: faster reconnect the first few times
        logger.debug('Connection closed')
        if self.die:
            return

        with self._ws_lock:
            if not self._ws:
                return
            self.logged_in = False
            self._ws = None

        self.reconnect()

    def close(self):
        self.logged_in = False
        self.die = True
        if self._ws:
            self._ws.close()

    def reconnect(self):
        logger.debug('Trying to reconnect a bit later')
        for _ in range(30):
            if self.die:
                return
            time.sleep(1)
        self.connect()

    def register_client(self):
        self.send_command('register',
                         self.player_id,
                         self.name,
                         self.commands,
                         self.options,
        )
        self.logged_in = True
        self.sent_full_state = False

    def _on_open(self, ws):
        logger.debug('Connection opened')
        self.register_client()

    def send_command(self, method, *args):
        logger.debug('Sending method %s with args %r' % (method, args))

        rpcid = random_id()
        self._ws.send(dumps(args, method, rpcid=rpcid))

        return rpcid
