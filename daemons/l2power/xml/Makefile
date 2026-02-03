# KTLXML definition of the keywords associated with this service.
#

include ../../Mk.instrument
include ../Mk.service

override SYSNAM = kss/$(INSTRUMENT)/$(KTLSERVICE)/xml
override VERNUM = 1.0

MAKEFLAGS += -j4
SUBST_STRICT = True

DEF_DIR = ../def

PDU = stripA1
PDU_DEFS = $(PDU:%=$(DEF_DIR)/%.defs)
PDU_STRIPS = $(PDU_DEFS:$(DEF_DIR)/%.defs=%)
PDU_DISP_XML = $(PDU_STRIPS:%=%_dispatcher.xml)
PDU_STRIP_XML = $(PDU_STRIPS:%=%_strip.xml)
PDU_OUTLETS_XML = $(PDU_STRIPS:%=%_outlets.xml)

# TEMPLATES = $(RELDIR)/data/kpdu
# TEMPLATE_IN = Dispatcher.xml.in index.xml.in Outlets.xml.in Strip.xml.in

KTLXML_FAMILY_SERVICE = $(KTLSERVICE)
KTLXML_DEPS = Makefile ../Mk.service index.xml

RELDAT = $(PDU_DISP_XML) $(PDU_STRIP_XML) $(PDU_OUTLETS_XML)
RELDAT += index.xml messages.xml keyword_ids.xml
DATSUB = $(KTLSERVICE)/xml

# FILES = $(RELDAT) $(TEMPLATE_IN)
FILES = $(RELDAT)
PREFILES = $(FILES)
PREINSTALL = $(PREFILES)

DIRS = dtune ktldisp


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

WAPP = $(RELDIR)/bin/wapp -x -We -F

$(PDU_DISP_XML): %_dispatcher.xml: $(DEF_DIR)/%.defs
	$(WAPP) -DRELDIR="$(RELDIR)" -f $(DEF_DIR)/$*.defs ./dispatcher.xml.sin $@

$(PDU_STRIP_XML): %_strip.xml: $(DEF_DIR)/%.defs
	$(WAPP) -DRELDIR="$(RELDIR)" -f $(DEF_DIR)/$*.defs ./pdu_strip.xml.sin $@

$(PDU_OUTLETS_XML): %_outlets.xml: $(DEF_DIR)/%.defs
	$(WAPP) -DRELDIR="$(RELDIR)" -f $(DEF_DIR)/$*.defs ./pdu_outlets.xml.sin $@

# index.xml: index.xml.in $(PDU_DEFS)
# 	$(WAPP) -DKTLSERVICE=$(KTLSERVICE) -DSTRIPS="$(STRIPS)" ./index.xml.in $@

index.xml: index.xml.sin $(UPS_DEFS)
	$(WAPP) -DKTLSERVICE=$(KTLSERVICE) -DSTRIPS="$(PDU_STRIPS)" ./index.xml.sin $@
