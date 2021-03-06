#!/usr/bin/env python
"""
Launch a serf node.

The role of the node is retrieved from the environment variable ``ROLE``.

The node will join a cluster, if the ``CONTACT`` variable specifies an
address.

"""

import subprocess
import time
import os
import multiprocessing

from utils import get_ports, encode_ports
import config
import docker_utils
from handler import MyHandler


def async_hook():
    p = multiprocessing.Process(target=hook)
    p.start()


def hook():
    ready_files = ['/agent_up', '/children_by_name.json']
    while not all(os.path.exists(f) for f in ready_files):
        time.sleep(0.1)
    MyHandler.init()


def main():
    role = config.role
    cmd = ('serf agent -event-handler=/handler/handler.py '
           '-log-level=debug -tag'
           .format(**locals()).split())
    cmd.append('role={role}'.format(**locals()))

    contact = config.peer
    if contact:
        cmd.extend(['-join', contact])

    ip = config.ip
    bind_port = config.bind_port

    cmd.extend(['-advertise', '{}:{}'.format(ip, bind_port)])
    cmd.extend(['-tag', 'ip={}'.format(ip),
                '-tag', 'serf_port={}'.format(bind_port)])
    cmd.extend(['-bind', '0.0.0.0:{}'.format(bind_port)])

    node = config.node
    cmd.extend(['-node', node])

    rpc_port = config.rpc_port
    cmd.extend(['-rpc-addr', '127.0.0.1:{}'.format(rpc_port)])
    cmd.extend(['-tag', 'rpc={}'.format(rpc_port)])
    cmd.extend(['-tag', 'timestamp={}'.format(time.time())])

    service = config.service or ip
    cmd.extend(['-tag', 'service={}'.format(service)])

    service_port = config.service_port
    cmd.extend(['-tag', 'service_port={}'.format(service_port)])

    cmd.extend(['-tag', 'ports={}'.format(
        encode_ports(get_ports()['ports']))])

    async_hook()

    subprocess.check_call(cmd)


if __name__ == '__main__':
    main()
