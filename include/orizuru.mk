
INCLUDE = include

PROJECT = $(shell basename $(PWD))

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
RUNSTAGE_TOUCH = touch "$(TMPDIR)/.SUCCESS_$(@)"

RUNSTAGE = $(RUNSTAGE_CHECK) || $(FAB) && $(RUNSTAGE_TOUCH)

RUNSTAGE_IGNORE_FAILURES = $(RUNSTAGE_CHECK) || $(FAB) || true && $(RUNSTAGE_TOUCH)

REQUIREMENTS = $(INCLUDE)/requirements.txt

preflight: pipinstalled pipdeps
	env | grep ^OS_MIDOKURA_ROOT_PASSWORD
	env | grep ^CONFIGFILE
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

removedestroycontainerslock:
	rm -f "$(TMPDIR)/.SUCCESS_destroycontainers"

destroycontainers: removedestroycontainerslock
	@echo
	@echo this will DESTROY all running containers and intermediate images on your hosts
	@echo
	@echo PRESS CTRL-C NOW
	@echo
	@sleep 10
	@echo
	@echo LAST CHANCE.
	@echo
	@sleep 10
	$(RUNSTAGE_IGNORE_FAILURES)

