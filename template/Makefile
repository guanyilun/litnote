# Render the notes as HTML and check that the code is tangled from them.
# The rules live in the shared litnote repo; `make list` shows what they see.

LITNOTE := @LITNOTE@
CODE    := bin/*.py src/*.py scripts/*.sbatch scripts/*.sh diagrams/*.svg
RUN_NOTES := analysis/@NAME@.org
include $(LITNOTE)/mk/litnote.mk
