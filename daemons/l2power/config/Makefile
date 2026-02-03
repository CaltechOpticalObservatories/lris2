# Config files for the KTL dispatcher.

include ../Mk.service
include ../../Mk.instrument

override SYSNAM = kss/$(INSTRUMENT)/$(KTLSERVICE)/config
override VERNUM = 1.0

MAKEFLAGS += -j4
SUBST_STRICT = True

DEF_DIR = ../def

#UPS_DEFS = $(DEF_DIR)/rspec1.defs
#UPS_CONFIG = $(UPS_DEFS:$(DEF_DIR)/%.defs=$(KTLSERVICE)_%.conf)
#UPS_STDIOSVC = $(UPS_DEFS:$(DEF_DIR)/%.defs=$(KTLSERVICE)_%_stdiosvc.conf)

PDU_DEFS = $(DEF_DIR)/stripA1.defs
PDU_CONFIG = $(PDU_DEFS:$(DEF_DIR)/%.defs=$(KTLSERVICE)_%.conf)
PDU_STDIOSVC = $(PDU_DEFS:$(DEF_DIR)/%.defs=$(KTLSERVICE)_%_stdiosvc.conf)

TEMPLATE_DIR = template
# UPS_TEMPLATE_IN = ups_ktlservice_dispnum.conf.in ktlservice_dispnum_stdiosvc.conf.in
TEMPLATE_IN = pdu_ktlservice_dispnum.conf.in ups_ktlservice_dispnum.conf.in ktlservice_dispnum_stdiosvc.conf.in

# PDU_DEFS = $(wildcard ../*_pdu.defs)
# PDU_DEFS = ../rspec2.defs
# PDU_CONFIG = $(PDU_DEFS:../%.defs=$(KTLSERVICE)_%.conf)
# PDU_STDIOSVC = $(PDU_DEFS:../%.defs=$(KTLSERVICE)_%_stdiosvc.conf)

# PDU_TEMPLATES = $(RELDIR)/data/kpdu
# PDU_TEMPLATE_IN = ktlservice_dispnum.conf.in ktlservice_dispnum_stdiosvc.conf.in

#RELDAT = $(UPS_CONFIG) $(UPS_STDIOSVC)
RELDAT = $(PDU_CONFIG) $(PDU_STDIOSVC)
DATSUB = $(KTLSERVICE)

# FILES = $(RELDAT) $(PDU_TEMPLATE_IN)
FILES = $(RELDAT)


################################################################################
# KROOT boilerplate:
# Include general make rules, using default values for the key environment
# variables if they are not already set.

ifndef KROOT
	KROOT = /kroot
endif

ifndef RELNAM
	RELNAM = default
endif

ifndef RELDIR
	RELDIR = $(KROOT)/rel/$(RELNAM)
endif

include $(KROOT)/etc/config.mk
################################################################################

# $(TEMPLATE_IN): %: $(TEMPLATE_DIR)/%
# 	$(RM) $@
# 	$(CP) $^ $@

# $(PDU_TEMPLATE_IN): %: $(PDU_TEMPLATES)/%
# 	$(RM) $@
# 	$(CP) $^ $@

WAPP = $(RELDIR)/bin/wapp -x -We -F

$(UPS_CONFIG): $(KTLSERVICE)_%.conf: $(DEF_DIR)/%.defs ./$(TEMPLATE_DIR)/ups_ktlservice_dispnum.conf.in
	$(WAPP) -DKROOT=$(KROOT) -DRELDIR=$(RELDIR) -f $(DEF_DIR)/$*.defs ./$(TEMPLATE_DIR)/ups_ktlservice_dispnum.conf.in $@

# $(UPS_STDIOSVC): $(KTLSERVICE)_%_stdiosvc.conf: ../%.defs ups_ktlservice_dispnum_stdiosvc.conf.in
# 	$(WAPP) -DKROOT=$(KROOT) -DRELDIR=$(RELDIR) -f ../$*.defs ./ups_ktlservice_dispnum_stdiosvc.conf.in $@

$(UPS_STDIOSVC): $(KTLSERVICE)_%_stdiosvc.conf: $(DEF_DIR)/%.defs ./$(TEMPLATE_DIR)/ktlservice_dispnum_stdiosvc.conf.in
	$(WAPP) -DKROOT=$(KROOT) -DRELDIR=$(RELDIR) -f $(DEF_DIR)/$*.defs ./$(TEMPLATE_DIR)/ktlservice_dispnum_stdiosvc.conf.in $@

# $(PDU_CONFIG): $(KTLSERVICE)_%.conf: ../%.defs ktlservice_dispnum.conf.in
# 	$(WAPP) -DKROOT=$(KROOT) -DRELDIR=$(RELDIR) -f ../$*.defs ./ktlservice_dispnum.conf.in $@

$(PDU_CONFIG): $(KTLSERVICE)_%.conf: $(DEF_DIR)/%.defs ./$(TEMPLATE_DIR)/pdu_ktlservice_dispnum.conf.in
	$(WAPP) -DKROOT=$(KROOT) -DRELDIR=$(RELDIR) -f $(DEF_DIR)/$*.defs ./$(TEMPLATE_DIR)/pdu_ktlservice_dispnum.conf.in $@

$(PDU_STDIOSVC): $(KTLSERVICE)_%_stdiosvc.conf: $(DEF_DIR)/%.defs ./$(TEMPLATE_DIR)/ktlservice_dispnum_stdiosvc.conf.in
	$(WAPP) -DKROOT=$(KROOT) -DRELDIR=$(RELDIR) -f $(DEF_DIR)/$*.defs ./$(TEMPLATE_DIR)/ktlservice_dispnum_stdiosvc.conf.in $@
