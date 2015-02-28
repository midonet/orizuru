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
import sys

from orizuru.config import Config

from fabric.api import *
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

metadata = Config(os.environ["CONFIGFILE"])

def stage11():
    puts(yellow("adding ssh connections to local known hosts file"))
    for server in metadata.servers:
        puts(green("connecting to %s now and adding the key" % server))
        local("ssh -o StrictHostKeyChecking=no root@%s uptime" % metadata.servers[server]["ip"])

    execute(stage11)

@roles('all_servers')
def stage11():

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure(["gnome", "ubuntu-desktop", "xrdp"])

    run("""

cat>/root/.xsession<<EOF
gnome-session -session=Ubuntu-2d
EOF

chmod 0755 /root/.xsession

service gdm restart

exit 0

""")

    # TODO cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

