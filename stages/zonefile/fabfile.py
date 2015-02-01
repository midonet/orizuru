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

def zonefile():
    metadata = Config(os.environ["CONFIGFILE"])

    Orizuru(metadata).zonefile()

    sys.exit(0)

