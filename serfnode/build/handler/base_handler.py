import yaml
import json
import os
import socket
import fcntl
import struct

from serf_master import SerfHandler
from utils import with_payload, truncated_stdout, with_member_info
from info import NODE_INFO, NODE_PORTS
import supervisor
import docker_utils
import utils
import serf


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


def collect_app_volumes():
    """Construct -v parameter to mount volumes in app."""

    app_volumes = os.environ.get('APP_VOLUMES')
    return (' '.join('-v {}'.format(vol)
                     for vol in yaml.load(app_volumes))
            if app_volumes else '')


def collect_app_volumes_from():
    """Construct --volumes_from parameter to mount volumes in app."""

    app_volumes_from = os.environ.get('APP_VOLUMES_FROM')
    return (' '.join('--volumes-from {}'.format(vol)
                     for vol in yaml.load(app_volumes_from))
            if app_volumes_from else '')


class BaseHandler(SerfHandler):

    def __init__(self, *args, **kwargs):
        super(BaseHandler, self).__init__(*args, **kwargs)
        self.volumes = collect_app_volumes()
        self.volumes_from = collect_app_volumes_from()
        self.all_volumes = self.volumes + self.volumes_from
        self.setup()
        self.notify()

    def setup(self):
        self.update()
        self.docker_run()
        self.spawn_children()

    def notify(self):
        with open('/agent_up', 'w') as f:
            f.write('')

    def docker_run(self):
        if docker_utils.DOCKER_RUN:
            supervisor.start('docker_run.conf', target='docker_run')

    def spawn_children(self):
        """Read /serfnode.yml and start containers"""

        if not os.path.exists('/serfnode.yml'):
            return

        with open('/serfnode.yml') as input:
            containers = yaml.load(input)
            for name, run_stmt in containers.items():
                supervisor.start_docker(name, run_stmt)

    @truncated_stdout
    @with_payload
    def where(self, role=None):
        my_role = os.environ.get('ROLE') or 'no_role'
        if my_role == role:
            print(NODE_INFO)

    @truncated_stdout
    @with_payload
    def ports(self, role=None):
        my_role = os.environ.get('ROLE') or 'no_role'
        if my_role == role:
            print(json.dumps(NODE_PORTS))

    def update(self):
        etc = utils.read_etc_hosts()
        new = serf.serf_all_hosts()
        recent = serf.serf_recent_hosts(new)
        etc.update(recent)
        utils.write_etc_hosts(etc)

    @with_member_info
    def member_join(self, members):
        self.update()

    @with_member_info
    def member_failed(self, members):
        self.update()

    @with_member_info
    def member_leave(self, members):
        self.update()
