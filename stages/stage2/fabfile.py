
import os
import sys

from orizuru.config import Config

from fabric.api import *
from fabric.operations import reboot
from fabric.colors import red
from fabric.utils import puts

def stage2():
    metadata = Config(os.environ["CONFIGFILE"])

    env.warn_only = True
    env.connection_attempts = 2
    env.timeout = 2
    env.skip_bad_hosts = True
    execute(reboot_stage2)
    env.warn_only = False

@parallel
@roles('all_servers')
def reboot_stage2():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(red("rebooting %s" % env.host_string))

    reboot()

