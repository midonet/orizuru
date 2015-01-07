
#  __  __ _     _                  _
# |  \/  (_) __| | ___  _ __   ___| |_
# | |\/| | |/ _` |/ _ \| '_ \ / _ \ __|
# | |  | | | (_| | (_) | | | |  __/ |_
# |_|  |_|_|\__,_|\___/|_| |_|\___|\__|
#

#
# Run Midonet Openstack on top of Ubuntu Docker ssh images.
#

all: info start passwordcache preflight stage1 stage3 stage4 stage5 stage6 stage7 success finish

include include/$(shell basename $(PWD)).mk

passwordcache:
	test -f $(PASSWORDCACHE) || $(BINDIR)/mkpwcache.sh | tee $(PASSWORDCACHE)

preflight: pipinstalled pipdeps

stage1sshconfig:
	mkdir -pv $(shell dirname $(SSHCONFIG))
	$(FAB) > $(SSHCONFIG)

stage1: stage1sshconfig
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

info:
	@clear
	@$(RUNSTAGE)
	@rm $(TMPDIR)/.SUCCESS_$(@)
	@sleep 10

stage2:
	$(RUNSTAGE)
	rm $(TMPDIR)/.SUCCESS_$(@)

stage3:
	mkdir -pv "$(TMPDIR)/etc/tinc"
	$(RUNSTAGE)

stage4:
	$(RUNSTAGE)

stage5:
	test -f "$(TMPDIR)/.SUCCESS_$(@)" || $(FAB)pingcheck
	$(RUNSTAGE)

stage6:
	mkdir -pv $(TMPDIR)/img
	cp img/favicon.ico $(TMPDIR)/img/favicon.ico
	cp img/midokura.png $(TMPDIR)/img/midokura.png
	$(RUNSTAGE)

stage7:
	$(RUNSTAGE)

start:
	mkdir -pv $(TMPDIR)
	@date > $(TMPDIR)/.START

finish:
	@date > $(TMPDIR)/.FINISH

success:
	@echo
	@echo your system is ready.
	@echo
	@grep ADMIN_PASS tmp/passwords.txt
	@echo
	@echo "horizon is at: http://$(shell grep -A6 openstack_horizon_ $(TMPDIR)/.ssh/config | tail -n1 | awk -F'root@' '{print $$2;}')/horizon/"
	@echo

clean: cleanlocks
	test -n "$(TMPDIR)" && rm -rfv "$(TMPDIR)"/.SUCCESS_*

cleanlocks:
	$(FAB) || true

cleancontainerlocks:
	$(FAB) || true

distclean: removedestroycontainerslock destroycontainers clean
	test -n "$(TMPDIR)" && rm -rfv "$(TMPDIR)"
	mkdir -pv "$(TMPDIR)"
	find $(SRCDIR) -type f -path '*.pyc' -delete
	make stage1sshconfig
