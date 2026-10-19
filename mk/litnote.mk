# Shared rules for literate org projects.  A project Makefile sets a few
# variables and includes this file:
#
#   LITNOTE  := $(HOME)/software/litnote
#   CODE     := bin/*.py src/*.py scripts/*.sbatch scripts/*.sh
#   RUN_NOTES := analysis/inputs.org analysis/compare.org # dependency order
#   include $(LITNOTE)/mk/litnote.mk
#
#   make                 notes + readme -> $(OUTDIR) (default out/notes)
#   make out/notes/X.html               one file
#   make check           blocks with no output, stale excerpts, rebinds
#   make tangle          write every :tangle block out to its file
#   make check-tangled   every CODE file is tangled from a note, none hand-edited
#   make runs            run every :run cell of the notes, in order (RUNS_ARGS passes options)
#   make runs-list       list them without running
#   make clean
#
# OUTDIR sets where the HTML goes; LEGACY_FLAT=no keeps legacy notes/ as a
# sub-folder of it (default: flat, for old URLs).
#
# Export never re-runs babel blocks (lisp/export-note.el); it ships what is
# already in the buffer or #+INCLUDEd from files the runs wrote.

LITNOTE ?= $(patsubst %/mk/,%,$(dir $(lastword $(MAKEFILE_LIST))))
EMACS   ?= emacs
PYTHON  ?= python3
OUTDIR  ?= out/notes
NOTES   ?= $(wildcard note/*.org analysis/*.org notes/*.org)
# Explicit dependency order, independent of document/index order.
RUN_NOTES ?= $(wildcard analysis/*.org note/*.org notes/*.org)
SRC     ?= $(NOTES) $(wildcard readme.org)
CODE    ?= bin/*.py src/*.py scripts/*.sbatch scripts/*.sh

LN_EL    := $(LITNOTE)/lisp/export-note.el $(LITNOTE)/lisp/review-comments.html
LN_POST  := $(LITNOTE)/py/highlight-html.py $(LITNOTE)/py/inline-images.py
LN_CHECK := $(LITNOTE)/py/check-results.py $(LITNOTE)/py/check-excerpts.py $(LITNOTE)/py/check-rebinds.py
LN_BATCH  = $(EMACS) -Q --batch -l $(LITNOTE)/lisp/export-note.el \
            --eval '(setq note/legacy-flat $(if $(ln_flat),t,nil))' --eval

# Preserve the new source directories.  Legacy notes/x.org renders flat to
# $(OUTDIR)/x.html, keeping old URLs, unless LEGACY_FLAT is no; then it
# keeps its directory like note/ and analysis/.
LEGACY_FLAT ?= yes
ln_flat  = $(filter yes,$(LEGACY_FLAT))
ln_html  = $(OUTDIR)/$(if $(ln_flat),$(patsubst notes/%,%,$(1:.org=.html)),$(1:.org=.html))
HTML    := $(foreach s,$(SRC),$(call ln_html,$(s)))

.PHONY: html check clean list tangle check-tangled litnote-version runs runs-list
.DEFAULT_GOAL := html

html: $(HTML)

check:
	@$(PYTHON) $(LITNOTE)/py/check-results.py $(SRC)
	@$(PYTHON) $(LITNOTE)/py/check-excerpts.py --quiet $(SRC) || true
	@$(PYTHON) $(LITNOTE)/py/check-rebinds.py $(SRC) || true

# Emacs writes the export next to the source, so build there and move.
# Figures are inlined as base64, leaving one portable file.
define ln_export_rule
$(call ln_html,$(1)): $(1) $(LN_EL) $(LN_POST) $(LN_CHECK) | $(OUTDIR)
	@$$(PYTHON) $(LITNOTE)/py/check-results.py $(1)
	@$$(PYTHON) $(LITNOTE)/py/check-excerpts.py --quiet $(1) || true
	@$$(PYTHON) $(LITNOTE)/py/check-rebinds.py $(1) | grep -v '^.*no hazardous' || true
	$$(LN_BATCH) '(note/export-html "$(1)")'
	mkdir -p $$(dir $$@)
	mv $(basename $(1)).html $$@
	$$(PYTHON) $(LITNOTE)/py/highlight-html.py $$@
	$$(PYTHON) $(LITNOTE)/py/inline-images.py $$@
endef
$(foreach s,$(SRC),$(eval $(call ln_export_rule,$(s))))

# The review document #+INCLUDEs the other notes, so it is stale when any changes.
ifdef REVIEW
$(call ln_html,$(REVIEW)): $(filter-out $(REVIEW),$(NOTES))
endif

$(OUTDIR):
	mkdir -p $@

list:
	@echo "sources: $(SRC)"
	@echo "html:    $(HTML)"
	@echo "code:    $(CODE)"

clean:
	rm -rf $(OUTDIR)

tangle:
	@for f in $(NOTES); do \
	  $(EMACS) -Q --batch -l org --eval "(org-babel-tangle-file \"$$f\")" 2>&1 | grep -v "^Loading"; done

check-tangled:
	@$(PYTHON) $(LITNOTE)/py/check-tangled.py $(CODE)

litnote-version:
	@git -C $(LITNOTE) describe --always --dirty

# RUN_NOTES controls execution, independently of presentation.
# REVIEW remains supported for existing projects.
LN_RUNS = $(PYTHON) $(LITNOTE)/py/run-cells.py $(if $(REVIEW),--review $(REVIEW),--notes $(RUN_NOTES))
runs:
	@$(LN_RUNS) $(RUNS_ARGS)

runs-list:
	@$(LN_RUNS) --dry-run $(RUNS_ARGS)
