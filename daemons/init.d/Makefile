# UCO "standard" start/stop configuration. Because of the value for DATSUB
# these files cannot be in the parent directory.

include ../Mk.instrument

SUBST_STRICT = True

RELBIN = lris2

RELDAT = instrument.env.sh lickStartStop.conf std_script.conf
DATSUB = $(INSTRUMENT)/init


POWDISPATCHERS = stripA
POWERSTHATBE = $(POWDISPATCHERS:%=l2power_%)

# INIT_COMMANDS = fakedcs l2ssd
INIT_COMMANDS = l2ssd
INIT_COMMANDS += $(POWERSTHATBE)
# INIT_COMMANDS += $(GREEN) $(RED) $(METS) $(POWERSTHATBE) $(CALS)

RELETC = $(INIT_COMMANDS)
ETCSUB = init.d

FILES = $(RELBIN) $(RELETC) generic_component instrument.env.sh std_script.conf

override SYSNAM = kss/$(INSTRUMENT)/init.d/standard/
override VERNUM = 1.0

################################################################################
# KROOT boilerplate:
# Include general make rules, using default values for the key environment
# variables if they are not already set.

ifndef KROOT
	KROOT = /kroot
endif

include $(RELDIR)/etc/defs.mk
################################################################################

ifeq "$(DS9)" ""
	DS9 := ds9
endif

################################################################################
include $(RELDIR)/etc/rules.mk
################################################################################

WAPP = $(RELDIR)/bin/wapp -x -F -w

$(INIT_COMMANDS): generic_component
	$(RM) $@ && cp $< $@

#	$(WAPP) -f ../HostInfo $@.in $@
