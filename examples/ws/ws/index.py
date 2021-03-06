import datetime
import json
import logging
import signal
import sys

import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.websocket import WebSocketHandler

from iotedgedriverlinksdk import getLogger
from iotedgedriverlinksdk.client import Config, SubDevice, getConfig
from iotedgedriverlinksdk.edge import (add_topo, delete_topo, get_topo,
                                       register_device,
                                       set_on_status_change_callback,
                                       set_on_topo_change_callback)
from iotedgedriverlinksdk.exception import (
    BaseEdgeException, EdgeDriverLinkDeviceOfflineException,
    EdgeDriverLinkException, EdgeDriverLinkOfflineException,
    EdgeDriverLinkTimeoutException)

log = getLogger()
log.setLevel(logging.DEBUG)


class WebSocketSever(WebSocketHandler):
    def check_origin(self, origin):
        return True

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")  # 这个地方可以写域名
        self.set_header("Access-Control-Allow-Headers", "*")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def initialize(self, loop):
        self.loop = loop
        self.client_id = ''
        self.product_sn = ''
        self.device_sn = ''
        self.client = SubDevice()

    def on_message_callback(self, topic, msg):
        self.write_message(str(msg))

    def open(self):
        try:
            product_sn = self.get_argument('product_sn')
            device_sn = self.get_argument('device_sn')
            log.info("websocket connect from: {}.{}".format(
                product_sn, device_sn))
            self.product_sn = product_sn
            self.device_sn = device_sn
            self.client_id = product_sn+'.'+device_sn

            self.client.set_product_sn(product_sn)
            self.client.set_device_sn(device_sn)
            self.client.login()

            self.client.set_msg_callback(self.on_message_callback)

            self.write_message('login success')

        except Exception as e:
            self.close(reason=str(e))

    def on_message(self, message):
        try:
            if self.client_id == '' or self.client is None:
                self.client.logout()
                self.close(reason='unknown client identify')
                return

            data = json.loads(message)
            log.info("websocket [{}] from:{}".format(
                data, self.client_id))

            if 'action' in data:
                action = data['action']
                if action == 'add_topo':
                    add_topo(self.product_sn, self.device_sn)
                elif action == 'delete_topo':
                    delete_topo(self.product_sn, self.device_sn)
                elif action == "logout":
                    self.client.logout()
                    self.close(reason='client exit')
                    return
                elif action == 'get_topo':
                    topo = get_topo()
                    self.write_message(topo)

            elif 'topic' in data and 'payload' in data:
                payload = data['payload']
                if isinstance(payload, dict):
                    byts = json.dumps(payload)
                    log.info('send time:{}'.format(
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')))
                    self.client.publish(
                        topic=data['topic'], payload=byts.encode('utf-8'))
                    log.info('send time:{}'.format(
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')))
                elif isinstance(payload, str):
                    byts = payload.encode('utf-8')
                    log.info('send time:{}'.format(
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')))
                    self.client.publish(
                        topic=data['topic'], payload=byts)

            else:
                print('unknown message')
        except Exception as e:
            self.client.logout()
            self.close(reason=str(e))

    def allow_draft76(self):
        return True

    def on_close(self):
        self.client.logout()
        log.info("websocket closed from:{}, with reason: {}".format(
            self.client_id, self.close_reason))


class Application(tornado.web.Application):
    def __init__(self, handlers, setting):
        super(Application, self).__init__(handlers, **setting)


def main():
    from tornado.platform.asyncio import AnyThreadEventLoopPolicy
    import asyncio

    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())
    lo = tornado.ioloop.IOLoop.current()
    handlers = [
        (r"/ws", WebSocketSever, dict(loop=lo))
    ]
    setting = dict(xsrf_cookies=False)
    app = Application(handlers, setting)
    app.listen(port=4567)
    print("websocket start listen port on:{}".format('4567'))
    lo.start()


def exit_handler(signum, frame):
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, exit_handler)
    signal.signal(signal.SIGTERM, exit_handler)
    main()
