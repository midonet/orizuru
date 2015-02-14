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

INCLUDE = include

ifeq "$(CONFIGFILE)" ""
CONFIGFILE = $(PWD)/conf/localhost.yaml
endif

SRCDIR = .

BINDIR = bin

CONFIGDIR = conf

ZONEFILE_TEMPLATE = $(CONFIGDIR)/zonefile.txt

ZONEFILE = $(TMPDIR)/zonefile.txt

HOSTSFILE = $(TMPDIR)/etc/hosts

SSHCONFIG = $(TMPDIR)/.ssh/config

PASSWORDCACHE = $(TMPDIR)/passwords.txt

LL = $(shell pwd)/lib

PP = PYTHONPATH="$(LL)"

CC = CONFIGFILE="$(CONFIGFILE)"

TT = TMPDIR="$(TMPDIR)"

PW = PASSWORDCACHE="$(PASSWORDCACHE)"

# AT = ADMIN_TOKEN="$(shell grep 'export ADMIN_TOKEN=' "$(PASSWORDCACHE)" | awk -F= '{print $$2;}' | xargs -n1 --no-run-if-empty echo)"

STAGES = stages

FABSSHCONFIG = --ssh-config-path=$(SSHCONFIG) --disable-known-hosts
FABFABFILE = --fabfile $(STAGES)/$(@)/fabfile.py

FAB = $(PP) $(CC) $(TT) $(PW) fab $(FABSSHCONFIG) $(FABFABFILE) $(@)

RUNSTAGE_CHECK = test -f "$(TMPDIR)/.SUCCESS_$(@)"
RUNSTAGE_TOUCH = date | tee "$(TMPDIR)/.SUCCESS_$(@)"

RUNSTAGE = figlet "running $(@)" || echo "running $(@)"; $(RUNSTAGE_CHECK) || $(FAB) && $(RUNSTAGE_TOUCH)

REQUIREMENTS = $(INCLUDE)/requirements.txt

preflight: pipinstalled pipdeps
	env | grep ^OS_MIDOKURA_ROOT_PASSWORD
	test -f $(CONFIGFILE)

TMPDIR = $(PWD)/tmp

$(TMPDIR):
	mkdir -pv "$(TMPDIR)"

pipinstalled:
	which pip || sudo apt-get -y install python-pip
	dpkg -l | grep ^ii | grep python-dev || sudo apt-get -y install python-dev
	dpkg -l | grep ^ii | grep python-yaml || sudo apt-get -y install python-yaml
	dpkg -l | grep ^ii | grep python-netaddr || sudo apt-get -y install python-netaddr

pipdeps: $(TMPDIR)
	test -f "$(TMPDIR)/.SUCCESS_pipinstall" || \
		sudo pip install --upgrade -r "$(REQUIREMENTS)" && \
		touch "$(TMPDIR)/.SUCCESS_pipinstall"

cleanup:
	@echo
	@echo this will DESTROY all running containers and intermediate images on your hosts
	@echo
	@echo PRESS CTRL-C NOW
	@echo
	@sleep 2
	@echo
	@echo LAST CHANCE.
	@echo
	@sleep 2
	$(FAB); echo

