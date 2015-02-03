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
from fabric.operations import reboot
from fabric.colors import red
from fabric.utils import puts

def poweroff():
    metadata = Config(os.environ["CONFIGFILE"])

    env.warn_only = True
    env.connection_attempts = 2
    env.timeout = 2
    env.skip_bad_hosts = True
    execute(poweroff_stage2)
    env.warn_only = False

@parallel
@roles('all_servers')
def poweroff_stage2():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(red("powering down %s" % env.host_string))

    run("""

poweroff

sleep 30

""")

