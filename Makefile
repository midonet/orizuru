
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

include include/$(shell basename $(PWD)).mk

passwordcache:
	test -f $(PASSWORDCACHE) || $(BINDIR)/mkpwcache.sh | tee $(PASSWORDCACHE)

preflight: pipinstalled pipdeps

stage1:
	mkdir -pv $(shell dirname $(SSHCONFIG))
	$(FAB)sshconfig > $(SSHCONFIG)
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

stage2:
	$(RUNSTAGE)

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
	@echo i think we are done here.
	@grep ADMIN_ tmp/passwords.txt
	@echo "horizon is at: http://$(shell grep -A2 openstack_horizon_ tmp/.ssh/config | tail -n1 | awk -F'-W' '{print $$2;}' | awk '{print $$1;}' | awk -F':' '{print $$1;}')/horizon/"
	@echo "midonet manager is at: http://$(shell grep -A2 midonet_manager_ tmp/.ssh/config | tail -n1 | awk -F'-W' '{print $$2;}' | awk '{print $$1;}' | awk -F':' '{print $$1;}')/midonet-cp2/"

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

