import json
import os
import socket
import fcntl
import struct

from serf_master import SerfHandler
from utils import with_payload, truncated_stdout, with_member_info
import docker_utils
import utils
import serf
import config

NODE_INFO = ''
NODE_PORTS = ''


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


def update_nodes_info():
    serf.all_nodes_by_role_and_id()


def get_info(cid):
    sid = serf.serf_json('info')['agent']['name']
    inspect = docker_utils.client.inspect_container(cid)
    return {'id': sid, 'inspect': inspect}


def save_me(loc):
    with open(loc, 'w') as f:
        json.dump(get_info(socket.gethostname()), f)


class BaseHandler(SerfHandler):

    def __init__(self, *args, **kwargs):
        super(BaseHandler, self).__init__(*args, **kwargs)
        save_me('/me.json')
        save_me('/serfnode/parent.json')
        self.setup()
        self.notify()

    def setup(self):
        self.update()

    def notify(self):
        with open('/agent_up', 'w') as f:
            f.write('')

    @truncated_stdout
    @with_payload
    def where(self, role=None):
        my_role = config.role
        if my_role == role:
            print(NODE_INFO)

    @truncated_stdout
    @with_payload
    def ports(self, role=None):
        my_role = config.role
        if my_role == role:
            print(json.dumps(NODE_PORTS))

    def update(self):
        etc = utils.read_etc_hosts()
        new = serf.serf_all_hosts()
        recent = serf.serf_recent_hosts(new)
        etc.update(recent)
        utils.write_etc_hosts(etc)
        update_nodes_info()

    @with_member_info
    def member_join(self, members):
        self.update()

    @with_member_info
    def member_failed(self, members):
        self.update()

    @with_member_info
    def member_leave(self, members):
        self.update()
