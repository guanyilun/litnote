;;; babel-setup.el --- make org-babel python failures visible  -*- lexical-binding: t -*-
;;
;; Load this before executing any of the notes:
;;
;;   (load "~/software/litnote/lisp/babel-setup.el")
;;
;; or add that line to ~/.emacs.d/lisp/init-org.el to get it everywhere.
;;
;; Problem it fixes
;; ----------------
;; With `:results output', a python session block that raises shows an *empty*
;; #+RESULTS: and no traceback.  ob-python wraps the body as
;;
;;     try:
;;         <exec the tempfile>
;;     except:
;;         raise
;;     finally:
;;         print('<end-of-execution marker>')
;;
;; and stops reading the process output at that marker.  The REPL prints the
;; traceback only after the exception finishes propagating, which is after the
;; marker has already been sent, so org never sees it.  Warnings are printed
;; during execution and do come through, which is why a block can show a
;; SyntaxWarning yet hide the NameError that killed it two lines later.
;;
;; The fix is to catch the exception inside the body and write the traceback to
;; stdout, before the marker is printed.

(require 'ob-python)

(setq org-babel-python--exec-tmpfile "\
import sys as __org_sys, traceback as __org_tb
try:
    with open('%s') as __org_babel_python_tmpfile:
        exec(compile(__org_babel_python_tmpfile.read(),
                     __org_babel_python_tmpfile.name, 'exec'))
except BaseException:
    __org_tb.print_exc(file=__org_sys.stdout)")

(provide 'babel-setup)
;;; babel-setup.el ends here
