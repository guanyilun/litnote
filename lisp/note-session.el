;;; note-session.el --- long-lived org-babel session for org notes  -*- lexical-binding: t -*-
;;
;; Keeps one Emacs daemon holding the note open with its python session alive,
;; so work can continue across separate commands instead of re-running the
;; whole buffer each time.
;;
;;   bin/note start                       ; emacs --daemon=note-<project>
;;   bin/note open notes/x.org
;;   bin/note stale                       ; what needs re-running
;;   bin/note run                         ; re-run just that
;;   bin/note py 'print(df.shape)'
;;   bin/note block fit-all
;;
;; ns/py evaluates in the *same* interpreter the note's blocks ran in, so
;; every variable they defined is still bound.
;;
;; Staleness
;; ---------
;; The blocks in a note share one interpreter and run in buffer order, so a
;; block's output depends on every block above it, not only on its own source.
;; That is what makes partial re-runs feel unsafe and pushes everything back
;; towards `ns/run-all', which reloads the data and costs minutes even when the
;; edit was a typo in the last block.
;;
;; `ns/run-stale' resolves that honestly.  After each run the sha1 of every
;; block's body is written to out/cache/<note>.hashes.el.  On the next call the
;; hashes are compared in order, and execution starts at the *first* block that
;; changed and continues to the end of the buffer.  Edit the appendix and only
;; the appendix re-runs; edit the setup block and everything re-runs, which is
;; the correct answer rather than a cautious one.  Inserting or deleting a
;; block shifts every later hash, so it re-runs the tail too -- again erring
;; towards running, never towards a note whose prose describes output that its
;; code no longer produces.
;;
;; `ns/stale' reports the same analysis without running anything, and also
;; names blocks whose #+RESULTS: is missing or empty.  An empty result is
;; nearly always a block that failed or never ran while the prose beneath it
;; went on quoting numbers, so it is worth seeing separately.

(require 'org)
(require 'ob-python)
(load (expand-file-name "babel-setup.el"
                        (file-name-directory (or load-file-name buffer-file-name))) nil t)

(defvar ns/file nil "Note currently held open by this daemon.")

(defun ns/open (file)
  "Open FILE and make its babel blocks executable in this daemon."
  (org-babel-do-load-languages
   'org-babel-load-languages '((emacs-lisp . t) (shell . t) (python . t)))
  (setq org-confirm-babel-evaluate nil)
  (setq ns/file (expand-file-name file))
  ;; Through ns/--buffer, never a bare find-file-noselect: if the daemon
  ;; already visits FILE and the file has been edited on disk since, the bare
  ;; call asks "changed on disk; reread?" in a minibuffer no one can answer,
  ;; and every later emacsclient call waits behind it.  That hung a session
  ;; for thirteen minutes on 2026-09-23.
  (ns/--buffer)
  (format "open: %s" ns/file))

(defun ns/--buffer ()
  "The note buffer, refreshed from disk without ever prompting.

A daemon has no frame on which to answer a yes-or-no prompt, so a single
confirmation deadlocks every later emacsclient call.  Clearing the modified
flag avoids find-file-noselect's \"changed on disk\" query, and binding
`revert-without-query' avoids revert-buffer's own."
  (let ((buf (find-file-noselect ns/file t)))
    (with-current-buffer buf
      (set-buffer-modified-p nil)
      (let ((revert-without-query (list (regexp-quote ns/file))))
        (revert-buffer t t t)))
    buf))

;;; ---------------------------------------------------------------- staleness

(defun ns/--hash-file ()
  "Where the per-block hashes for the current note are kept."
  (let ((dir (expand-file-name "../out/cache/" (file-name-directory ns/file))))
    (make-directory dir t)
    (expand-file-name (concat (file-name-base ns/file) ".hashes.el") dir)))

(defun ns/--blocks ()
  "One (POSITION LABEL HASH NAME NOEVAL) per source block, in buffer order.

NAME is the block's #+name: or nil.  LABEL is that name when it has one and
otherwise the heading it sits under, so `ns/stale' can print something that
is also a valid argument to `ns/section' or `ns/block'.  NOEVAL marks the
blocks that are meant to show nothing -- :eval no, an illustration of a
command rather than a run of it, and :results silent, a block that does its
work in the session and has nothing to say about it -- so that the empty
results report stays free of false positives and keeps being worth reading."
  (org-element-map (org-element-parse-buffer) 'src-block
    (lambda (el)
      (let ((name (org-element-property :name el))
            (params (or (org-element-property :parameters el) "")))
        (list (org-element-property :begin el)
              (or name
                  (let ((h (org-element-lineage el '(headline))))
                    (and h (org-element-property :raw-value h)))
                  "(top)")
              (secure-hash 'sha1 (or (org-element-property :value el) ""))
              name
              (and (string-match-p
                    ":eval\\s-+\\(no\\|never\\)\\b\\|:results\\s-[^:]*\\b\\(silent\\|none\\)\\b"
                    params)
                   t))))))

(defun ns/--saved-hashes ()
  (let ((f (ns/--hash-file)))
    (and (file-exists-p f)
         (with-temp-buffer (insert-file-contents f) (read (current-buffer))))))

(defun ns/--save-hashes (hashes)
  (with-temp-file (ns/--hash-file)
    (insert ";; sha1 of each source block as last executed by ns/run-stale.\n"
            ";; Delete this file to force the whole note to re-run.\n")
    (prin1 hashes (current-buffer))
    (insert "\n")))

(defun ns/--first-missing-result ()
  "Index of the first block that has no output, or nil.

Hashes alone are not enough.  A block's results can go missing while its body
stays byte-identical -- rewriting a whole section, or an editor mishap, takes
the results node with it -- and such a block looks perfectly fresh to a
comparison of bodies.  It is not fresh: the note is about to export a gap."
  (let ((i 0) (found nil))
    (save-excursion
      (dolist (b (ns/--blocks))
        (goto-char (nth 0 b))
        (when (and (null found) (not (nth 4 b)) (ns/--result-empty-p))
          (setq found i))
        (setq i (1+ i))))
    found))

(defun ns/--first-changed ()
  "Index of the first block that needs re-running, or nil.

Whichever comes first: a block whose body no longer matches the last run, or
a block with no output at all.  A note with no saved hashes is entirely
stale, so that returns 0."
  (let* ((was (ns/--saved-hashes))
         (changed (if (null was) 0
                    (ns/--mismatch (mapcar (lambda (b) (nth 2 b)) (ns/--blocks))
                                   was)))
         (missing (ns/--first-missing-result)))
    (cond ((null changed) missing)
          ((null missing) changed)
          (t (min changed missing)))))

(defun ns/--mismatch (a b)
  "Index of the first differing element of A and B, or nil when neither
runs out before they disagree."
  (let ((i 0) (found nil))
    (while (and (not found) (< i (min (length a) (length b))))
      (unless (equal (nth i a) (nth i b)) (setq found i))
      (setq i (1+ i)))
    (or found (and (/= (length a) (length b)) (min (length a) (length b))))))

(defun ns/--result-empty-p ()
  "Non-nil when the block at point produced nothing.
Point must be inside a source block."
  (save-excursion
    (let ((pos (org-babel-where-is-src-block-result)))
      (if (not pos)
          t
        (goto-char pos)
        (forward-line 1)
        (let ((line (string-trim (buffer-substring-no-properties
                                  (point) (line-end-position)))))
          (or (string-empty-p line) (string-prefix-p "*" line)))))))

(defun ns/stale ()
  "Report which blocks would re-run, and which produced no output.
Runs nothing."
  (with-current-buffer (ns/--buffer)
    (let* ((blocks (ns/--blocks))
           (from (ns/--first-changed))
           (empty '())
           (i 0))
      (save-excursion
        (dolist (b blocks)
          (goto-char (nth 0 b))
          (when (and (not (nth 4 b)) (ns/--result-empty-p))
            (push (format "  %2d  %s" i (nth 1 b)) empty))
          (setq i (1+ i))))
      (concat
       (if (null from)
           (format "up to date: all %d blocks match the last run\n" (length blocks))
         (format "stale from block %d (%s); %d of %d blocks would re-run\n"
                 from (nth 1 (nth from blocks)) (- (length blocks) from)
                 (length blocks)))
       (if empty
           (concat "blocks with no output:\n"
                   (mapconcat #'identity (nreverse empty) "\n") "\n")
         "every block has output\n")))))

(defun ns/--exec-range (from &optional to)
  "Execute blocks [FROM, TO) by index and record hashes.  TO defaults to the end.

Each execution inserts or rewrites a results node and so moves every block
below it, which is why the block list is rebuilt on each step rather than
walked once."
  (let* ((n (length (ns/--blocks)))
         (to (or to n))
         (i from))
    (while (< i to)
      (save-excursion
        (goto-char (nth 0 (nth i (ns/--blocks))))
        (org-babel-execute-src-block))
      (setq i (1+ i)))
    (ns/--save-hashes (mapcar (lambda (b) (nth 2 b)) (ns/--blocks)))
    (save-buffer)
    (- to from)))

(defun ns/run-stale ()
  "Re-run from the first changed block to the end of the note, and save.
This is the everyday command.  See the staleness note at the top of this
file for why it runs the tail rather than only the blocks you edited."
  (with-current-buffer (ns/--buffer)
    (let ((from (ns/--first-changed)))
      (if (null from)
          "nothing to do; every block matches the last run"
        (format "ran %d block(s), from %d to the end"
                (ns/--exec-range from) from)))))

(defun ns/run-all ()
  "Execute every block in the note and save.  Slow; prefer `ns/run-stale'."
  (with-current-buffer (ns/--buffer)
    (format "ran all %d blocks" (ns/--exec-range 0))))

(defun ns/run-from (heading)
  "Execute every block from HEADING to the end of the note, and save.
Use when the change is not in the source at all -- a script under bin/ that
a block shells out to, or a file it reads -- so the hashes cannot see it."
  (with-current-buffer (ns/--buffer)
    (let ((pos (save-excursion
                 (goto-char (point-min))
                 (or (re-search-forward
                      (concat "^\\*+ " (regexp-quote heading) "\\s-*$") nil t)
                     (error "No heading matching %S" heading))))
          (i 0) (from nil))
      (dolist (b (ns/--blocks))
        (when (and (null from) (> (nth 0 b) pos)) (setq from i))
        (setq i (1+ i)))
      (unless from (error "No blocks under or after %S" heading))
      (format "ran %d block(s), from %d to the end"
              (ns/--exec-range from) from))))

(defun ns/--refresh-hashes-for (indices)
  "Mark the blocks at INDICES as freshly run.

Only those blocks are touched, so a section run does not claim the rest of
the note is current.  If the buffer has gained or lost a block since the
last full run the indices no longer line up, and rather than write hashes
that quietly point at the wrong blocks this leaves the file as it was: the
note then still reads as stale from the edit onwards, which is true."
  (let ((was (ns/--saved-hashes))
        (now (ns/--blocks)))
    (when (and was (= (length was) (length now)))
      (dolist (i indices)
        (setf (nth i was) (nth 2 (nth i now))))
      (ns/--save-hashes was))))

(defun ns/--subtree-block-indices (heading)
  "Indices, in buffer order, of the source blocks under HEADING.

Indices rather than buffer positions: executing a block rewrites its results
node and moves everything below it, so a position captured before the run
points somewhere else after it.  The count and order of blocks do not
change, so an index survives."
  (save-excursion
    (goto-char (point-min))
    (unless (re-search-forward
             (concat "^\\*+ " (regexp-quote heading) "\\s-*$") nil t)
      (error "No heading matching %S" heading))
    (let ((beg (point)) (end (save-excursion (org-end-of-subtree t t)))
          (i -1))
      (delq nil (mapcar (lambda (b)
                          (setq i (1+ i))
                          (and (> (nth 0 b) beg) (< (nth 0 b) end) i))
                        (ns/--blocks))))))

(defun ns/section (heading)
  "Execute only the blocks under HEADING, in the session already running.
Re-running the whole buffer reloads the data; this does not.

This trusts you that nothing above HEADING matters.  When you are not sure,
`ns/run-stale' works the dependency out instead of assuming."
  (with-current-buffer (ns/--buffer)
    (let ((indices (ns/--subtree-block-indices heading)))
      (save-excursion
        (goto-char (point-min))
        (re-search-forward (concat "^\\*+ " (regexp-quote heading) "\\s-*$"))
        (org-babel-execute-subtree))
      (ns/--refresh-hashes-for indices)
      (save-buffer)
      (format "ran %d block(s) under %S" (length indices) heading))))

(defun ns/session-buffer ()
  "The live python comint buffer for the note, or nil."
  (with-current-buffer (ns/--buffer)
    (let ((name (cdr (assq :session
                           (nth 2 (save-excursion
                                    (goto-char (point-min))
                                    (org-babel-next-src-block)
                                    (org-babel-get-src-block-info t)))))))
      (get-buffer (format "*%s*" name)))))

(defun ns/py (code)
  "Evaluate CODE in the note's existing python session; return its stdout."
  (let ((buf (ns/session-buffer)))
    (unless buf
      (error "No live session; run (ns/run-all) first"))
    (org-babel-python-evaluate-session buf code 'output)))

(defun ns/py-file (path)
  "Evaluate the python in PATH in the note's session; return its stdout.
Quoting python through `emacsclient --eval' is unreliable, so put the code
in a file and pass the path."
  (ns/py (with-temp-buffer (insert-file-contents path) (buffer-string))))

(defun ns/block (&rest names)
  "Execute the blocks called NAMES (their #+name:), in the order given, and save.

The finest-grained of these commands, and the one to reach for when an edit
touches a few scattered blocks and you know nothing between them matters --
adding a helper to the setup block, say, and re-running only its callers.
Blocks have to be named for this to reach them."
  (with-current-buffer (ns/--buffer)
    (let ((indices '()))
      (dolist (name names)
        (let ((i 0) (hit nil))
          (dolist (b (ns/--blocks))
            (when (equal (nth 3 b) name) (setq hit i))
            (setq i (1+ i)))
          (unless hit (error "No block named %S" name))
          (push hit indices))
        (save-excursion
          (org-babel-goto-named-src-block name)
          (org-babel-execute-src-block)))
      (ns/--refresh-hashes-for indices)
      (save-buffer)
      (format "ran %d named block(s)" (length names)))))

(defun ns/sections (&rest headings)
  "Execute the blocks under each of HEADINGS, in order, in one session.
Running the whole buffer reloads the data and redoes the expensive work even
when only a later section changed.  Naming the sections avoids that; list
the cheap setup sections a later one depends on."
  (with-current-buffer (ns/--buffer)
    (let ((indices '()))
      (dolist (h headings)
        (setq indices (append indices (ns/--subtree-block-indices h)))
        (save-excursion
          (goto-char (point-min))
          (re-search-forward (concat "^\\*+ " (regexp-quote h) "\\s-*$"))
          (org-babel-execute-subtree)))
      (ns/--refresh-hashes-for indices)
      (save-buffer)
      (format "ran %d block(s) across %d section(s)"
              (length indices) (length headings)))))

(defun ns/status ()
  "Report whether the session is alive and what it is holding."
  (let ((buf (ns/session-buffer)))
    (format "file=%s session=%s alive=%s"
            (file-name-nondirectory (or ns/file "none"))
            (if buf (buffer-name buf) "none")
            (and buf (process-live-p (get-buffer-process buf))))))

(provide 'note-session)
;;; note-session.el ends here
