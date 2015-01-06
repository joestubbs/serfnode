from __future__ import print_function

from functools import wraps
import json
import os
import sys
import time
import traceback
import cStringIO
import shutil
import socket

import mischief.actors.pipe as p
import mischief.actors.actor as a
import docker_utils


MAX_OUTPUT = 1000


def truncated_stdout(f):
    """Decorator to truncate stdout to final `MAX_OUTPUT` characters. """

    @wraps(f)
    def wrapper(*args, **kwargs):
        old_stdout = sys.stdout
        old_stdout.flush()
        sys.stdout = cStringIO.StringIO()
        out = ''
        try:
            result = f(*args, **kwargs)
            stdout = sys.stdout.getvalue()
            out = stdout + '\nSUCCESS' if stdout else ''
            return result
        except Exception:
            out = traceback.format_exc() + '\nERROR'
        finally:
            sys.stdout = old_stdout
            print(out[-MAX_OUTPUT:], end='')
    return wrapper


def with_payload(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        payload = json.loads(sys.stdin.read())
        kwargs.update(payload)
        return f(*args, **kwargs)
    return wrapper


def with_member_info(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        kwargs['members'] = list(member_info(sys.stdin.readlines()))
        return f(*args, **kwargs)
    return wrapper


def member_info(lines):
    for line in lines:
        member = {}
        parts = line.split()
        member['node'] = parts[0]
        member['ip'] = parts[1]
        member['role'] = parts[2]
        member['tags'] = dict(part.split('=') for part in parts[3].split(','))
        yield member


def save_info(node, advertise, bind_port, rpc_port):
    info = {
        'node': node,
        'ip': advertise,
        'bind_port': bind_port,
        'rpc_port': rpc_port
    }
    with open('/node_info', 'w') as out:
        json.dump(info, out)


def load_info():
    """Load information about the node.

    Block until the information is available.

    """
    while not os.path.exists('/node_info'):
        time.sleep(0.1)

    return json.load(open('/node_info'))


def serf_aware_spawn(actor, name, **kwargs):
    """Spawn actor and save address info in ``/actor_info``. """

    ip = os.environ.get('IP') or p.get_local_ip('8.8.8.8')
    kwargs['ip'] = ip
    proc = a.spawn(actor, **kwargs)
    try:
        os.makedirs('/actors')
    except OSError:
        pass
    with open('/actors/{}'.format(name), 'w') as f:
        identifier, ip, port = proc.address()
        json.dump({'name': identifier, 'ip': ip, 'port': port}, f)
    return proc


def read_etc_hosts():
    etc = [line.strip().split()
           for line in open('/etc/hosts').readlines()
           if not line.startswith('#')]
    return {host: line[0] for line in etc for host in line[1:]}


def write_etc_hosts(etc):
    shutil.copyfile('/etc/hosts', '/etc/hosts.orig')
    ip_hosts = {}
    for host, ip in etc.items():
        ip_hosts.setdefault(ip, []).append(host)
    with open('/etc/hosts', 'w') as f:
        f.writelines(
            ' '.join([ip] + hosts)+'\n' for ip, hosts in ip_hosts.items())


def get_ports():
    """Get the ports mapping for this node."""

    def _get_ports():
        cinfo = docker_utils.client.inspect_container(socket.gethostname())
        for port, host_ports in cinfo['NetworkSettings']['Ports'].items():
            if host_ports is not None:
                yield port, [host['HostPort'] for host in host_ports]

    return json.dumps({
        'ports': dict(_get_ports()),
        'ip': os.environ.get('IP') or p.get_local_ip('8.8.8.8')})
