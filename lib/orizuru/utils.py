#!/usr/bin/python -Werror

#
# Copyright (c) 2015 Midokura SARL, All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

from fabric.api import *

class Daemon(object):
    def __init__(self, configfile):
        pass

    @classmethod
    def poll(cls, daemon_string, timeout=15):
        run("""
DAEMON_STRING="%s"
TIMEOUT="%i"

RETURNCODE=1

for i in $(seq 1 "${TIMEOUT}"); do
    ALIVE="$(ps axufwwwwwwwwwwwwwwwwwwwwww | grep -v grep | grep "${DAEMON_STRING}")"

    if [[ "" == "${ALIVE}" ]]; then
        RETURNCODE=1
    else
        RETURNCODE=0
        continue
    fi

    sleep 2
done

exit "${RETURNCODE}"

""" % (daemon_string, timeout))

