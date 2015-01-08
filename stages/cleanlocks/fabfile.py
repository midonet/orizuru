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

def cleanlocks():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(clean_lockfiles_from_servers)
    #execute(clean_lockfiles_from_containers)

@parallel
@roles('all_servers')
def clean_lockfiles_from_servers():
    clean_lockfiles()

@parallel
@roles('all_containers')
def clean_lockfiles_from_containers():
    clean_lockfiles()

def clean_lockfiles():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(red("cleaning lockfiles from /tmp dir on %s" % env.host_string))

    run("""
rm -rfv /tmp/.*.lck
""")

