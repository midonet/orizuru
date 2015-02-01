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

passwordcache:
	test -f $(PASSWORDCACHE) || $(BINDIR)/mkpwcache.sh | tee $(PASSWORDCACHE)

preflight: pipinstalled pipdeps

dumpconfig:
	make sshconfig 2>&1

ci:
	bin/ci.sh

sshconfig:
	mkdir -pv $(shell dirname $(SSHCONFIG))
	$(FAB) > $(SSHCONFIG)

stage1: sshconfig
	@figlet UPGRADE SYSTEMS || true
	mkdir -pv $(shell dirname $(ZONEFILE))
	cat $(ZONEFILE_TEMPLATE) > $(ZONEFILE)
	$(FAB)zonefile >> $(ZONEFILE)
	mkdir -pv $(shell dirname $(HOSTSFILE))
	$(FAB)hostsfile > $(HOSTSFILE)
	./stages/$@/bin/localips.sh >> $(HOSTSFILE)
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)pingcheck
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)sshcheck
	$(RUNSTAGE)

reboot: stage2

info: sshconfig
	@clear
	@$(FAB):admin_password="$(shell grep ADMIN_PASS $(PASSWORDCACHE) | awk -F'=' '{print $$2;}')"
	@test -f $(TMPDIR)/.SUCCESS_stage1 || sleep 10

stage2: sshconfig
	$(RUNSTAGE)
	rm $(TMPDIR)/.SUCCESS_$(@)

stage3: sshconfig
	@figlet SET UP VPN || true
	mkdir -pv "$(TMPDIR)/etc/tinc"
	$(RUNSTAGE)

stage4: sshconfig
	@figlet CONFIGURE CONTAINERS || true
	$(RUNSTAGE)

stage5: sshconfig
	@figlet UPGRADE CONTAINERS || true
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)pingcheck
	$(RUNSTAGE)

stage6: sshconfig
	@figlet INSTALL OPENSTACK || true
	mkdir -pv $(TMPDIR)/img
	cp img/favicon.ico $(TMPDIR)/img/favicon.ico
	cp img/midokura.png $(TMPDIR)/img/midokura.png
	$(RUNSTAGE)

stage7: sshconfig
	@figlet INSTALL MIDONET || true
	$(RUNSTAGE)

#
# do not run this yet, it is still experimental
#
#stage8: sshconfig
#	$(RUNSTAGE)

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

clean: sshconfig cleanlocks
	test -n "$(TMPDIR)" && rm -rfv "$(TMPDIR)"/.SUCCESS_*

cleanlocks: sshconfig
	$(FAB) || true

cleancontainerlocks: sshconfig
	$(FAB) || true

distclean: sshconfig cleanup clean
	test -n "$(TMPDIR)" && rm -rfv "$(TMPDIR)"
	mkdir -pv "$(TMPDIR)"
	find $(SRCDIR) -type f -path '*.pyc' -delete
	make sshconfig
