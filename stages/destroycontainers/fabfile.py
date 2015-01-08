
import os
import sys

from orizuru.config import Config

from fabric.api import *

from fabric.colors import green, yellow, red
from fabric.utils import puts

import cuisine

from netaddr import IPNetwork as CIDR

def destroycontainers():
    metadata = Config(os.environ["CONFIGFILE"])

    execute(fabric_docker_rm_role_containers)

@parallel
@roles('all_servers')
def fabric_docker_rm_role_containers():
    metadata = Config(os.environ["CONFIGFILE"])

    for role in sorted(metadata.roles):
        if role <> 'all_servers':
            if env.host_string in metadata.roles[role]:
                puts(yellow("destroying container %s on %s" % (role, env.host_string)))
                run("""

SERVER_NAME="%s"
CONTAINER_ROLE="%s"

TEMPLATE_NAME="template_${SERVER_NAME}"

for CONTAINER in $(docker ps | grep "${CONTAINER_ROLE}_${SERVER_NAME}" | awk '{print $1;}' | grep -v CONTAINER); do
    docker kill $CONTAINER || true;
    docker rm -f $CONTAINER || true;
done

docker images | grep "${TEMPLATE_NAME}" && docker rmi -f "${TEMPLATE_NAME}" || true;

rm -fv /var/run/netns/docker_*_${SERVER_NAME} || true;

exit 0

""" % (env.host_string, role))

    #
    # brute force remove all containers and images
    #
    run("docker ps --no-trunc -aq | xargs -n1 --no-run-if-empty docker rm -f")
    run("docker images | grep '^<none>' | awk '{print $3}' | xargs -n1 --no-run-if-empty docker rmi -f")

