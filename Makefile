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

#  __  __ _     _                  _
# |  \/  (_) __| | ___  _ __   ___| |_
# | |\/| | |/ _` |/ _ \| '_ \ / _ \ __|
# | |  | | | (_| | (_) | | | |  __/ |_
# |_|  |_|_|\__,_|\___/|_| |_|\___|\__|
#

#
# Run Midonet Openstack on top of Ubuntu Docker ssh images.
#

all: start passwordcache preflight stage1 stage3 stage4 stage5 stage6 stage7 success finish

include include/orizuru.mk

PREREQUISITES = sshconfig zonefile etchosts

passwordcache:
	test -f $(PASSWORDCACHE) || $(BINDIR)/mkpwcache.sh | tee $(PASSWORDCACHE)

preflight: pipinstalled pipdeps

ci:
	bin/ci.sh

sshconfig:
	mkdir -pv $(shell dirname $(SSHCONFIG))
	$(FAB) > $(SSHCONFIG)

zonefile:
	mkdir -pv $(shell dirname $(ZONEFILE))
	cat $(ZONEFILE_TEMPLATE) > $(ZONEFILE)
	$(FAB) >> $(ZONEFILE)

etchosts:
	mkdir -pv $(shell dirname $(HOSTSFILE))
	$(FAB) > $(HOSTSFILE).NEW
	./stages/$@/bin/localips.sh >> $(HOSTSFILE).NEW
	mv $(HOSTSFILE).NEW $(HOSTSFILE)

stage1: $(PREREQUISITES)
	@figlet UPGRADE SYSTEMS || true
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)pingcheck
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)sshcheck
	$(RUNSTAGE)

reboot: stage2

poweroff: $(PREREQUISITES)
	$(RUNSTAGE); rm $(TMPDIR)/.SUCCESS_$(@)

rootlogins: $(PREREQUISITES)
	$(RUNSTAGE); rm $(TMPDIR)/.SUCCESS_$(@)

info: $(PREREQUISITES)
	@clear
	@$(FAB):admin_password="$(shell grep ADMIN_PASS $(PASSWORDCACHE) | awk -F'=' '{print $$2;}')"
	@test -f $(TMPDIR)/.SUCCESS_stage1 || sleep 10

stage2: $(PREREQUISITES)
	$(RUNSTAGE)
	rm $(TMPDIR)/.SUCCESS_$(@)

stage3: $(PREREQUISITES)
	@figlet SET UP VPN || true
	mkdir -pv "$(TMPDIR)/etc/tinc"
	$(RUNSTAGE)

stage4: $(PREREQUISITES)
	@figlet CONFIGURE CONTAINERS || true
	$(RUNSTAGE)

stage5: $(PREREQUISITES)
	@figlet UPGRADE CONTAINERS || true
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)pingcheck
	$(RUNSTAGE)

stage6: $(PREREQUISITES)
	@figlet INSTALL OPENSTACK || true
	mkdir -pv $(TMPDIR)/img
	cp img/favicon.ico $(TMPDIR)/img/favicon.ico
	cp img/midokura.png $(TMPDIR)/img/midokura.png
	$(RUNSTAGE)

stage7: $(PREREQUISITES)
	@figlet INSTALL MIDONET || true
	$(RUNSTAGE)

#
# tempest
#
stage8: $(PREREQUISITES)
	@figlet TEMPEST || true
	$(RUNSTAGE)

#
# swift
#
stage9: $(PREREQUISITES)
	@figlet SWIFT || true
	$(RUNSTAGE)

#
# vtep logic
#
stage10: $(PREREQUISITES)
	@figlet VTEP || true
	$(RUNSTAGE)

uptime: $(PREREQUISITES)
	$(RUNSTAGE)
	rm $(TMPDIR)/.SUCCESS_$(@)

start:
	mkdir -pv $(TMPDIR)
	@date > $(TMPDIR)/.START

finish:
	@date > $(TMPDIR)/.FINISH

success:
	@echo
	@echo your system is ready.
	@echo
	@echo run \'make info\' to see the urls and admin password
	@echo

clean: $(PREREQUISITES) cleanlocks
	test -n "$(TMPDIR)" && rm -rfv "$(TMPDIR)"/.SUCCESS_*

cleanlocks: $(PREREQUISITES)
	$(FAB) || true

cleancontainerlocks: $(PREREQUISITES)
	$(FAB) || true

distclean: $(PREREQUISITES) cleanup clean
	test -n "$(TMPDIR)" && rm -rfv "$(TMPDIR)"
	mkdir -pv "$(TMPDIR)"
	find $(SRCDIR) -type f -path '*.pyc' -delete
	make $(PREREQUISITES)

