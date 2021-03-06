#!/usr/bin/env python

import json
import time
import os

import pipe
from base_handler import get_info


def handler(obj):
    try:
        old = json.load(open('/children_by_name.json'))
    except IOError:
        old = {}
    while not os.path.exists('/agent_up'):
        time.sleep(0.1)
    new = get_info(obj)
    name = new['inspect']['Name'][1:]
    old[name] = new
    with open('/children_by_name.json', 'w') as f:
        json.dump(old, f)


if __name__ == '__main__':
    pipe.server('/tmp/children_server', handler)
