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

from orizuru.operations import Configure
from orizuru.operations import Install

from orizuru.common import Orizuru

from fabric.api import *
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

from netaddr import IPNetwork as CIDR

def stage1pingcheck():
    metadata = Config(os.environ["CONFIGFILE"])

    Orizuru(metadata).pingcheck()

def stage1zonefile():
    metadata = Config(os.environ["CONFIGFILE"])

    Orizuru(metadata).zonefile()

    # do not remove this or you will have the word "Done." in your zonefile (thanks fabric)
    sys.exit(0)

def stage1hostsfile():
    metadata = Config(os.environ["CONFIGFILE"])

    Orizuru(metadata).hostsfile()

    # do not remove this.
    sys.exit(0)

def stage1sshcheck():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("executing stage1 connection check"))
    execute(connect_stage1)

@parallel
@roles('all_servers')
def connect_stage1():
    metadata = Config(os.environ["CONFIGFILE"])

    Orizuru(metadata).connectcheck()

def stage1():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("executing stage1 configure"))
    execute(configure_stage1)

    puts(yellow("executing stage1 install"))
    execute(install_stage1)

    sys.exit(0)

@parallel
@roles('all_servers')
def configure_stage1():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    Configure(metadata).configure()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@parallel
@roles('all_servers')
def install_stage1():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    Install(metadata).install()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

