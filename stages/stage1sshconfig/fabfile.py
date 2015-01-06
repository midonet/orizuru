
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

def stage1sshconfig():
    metadata = Config(os.environ["CONFIGFILE"])

    Orizuru(metadata).sshconfig()

    # do not remove this.
    sys.exit(0)

