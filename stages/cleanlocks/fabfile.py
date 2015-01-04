
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

