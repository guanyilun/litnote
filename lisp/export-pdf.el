;;; export-pdf.el --- batch org -> LaTeX for a PDF of one note  -*- lexical-binding: t -*-
;;
;; Used by mk/litnote.mk (`make out/notes/x.pdf'); not meant to be loaded
;; interactively.
;;
;;   emacs -Q --batch -l $LITNOTE/lisp/export-pdf.el \
;;         --eval '(note/export-latex "note/x.org")'
;;
;; writes note/x.tex; make runs latexmk -xelatex on it and moves the PDF to
;; the output folder.  A PDF is one self-contained file, for readers who get
;; the note without the project (no image files, no links to other notes).
;;
;; It reuses export-note.el's settings (babel off: ship what the runs wrote)
;; and its notebook reading, as plain-text labels: "-> FILE" over a tangled
;; block, "run" over a :run cell, "output" over its output.  What the HTML
;; does in the browser is laid out on paper instead:
;;   - a figure with :data-frames shows every frame, stacked, each under its
;;     label from :data-labels;
;;   - a figure with :data-swipe shows the two images one under the other,
;;     labelled with :data-swipe-labels;
;;   - code and outputs are listings that wrap long lines; an output's font
;;     shrinks with its widest line, so report tables keep their columns.
;; XeLaTeX with the DejaVu fonts, so Greek, degrees, primes and arrows in the
;; prose, captions and code print as they are.

(load (expand-file-name "export-note.el" (file-name-directory (or load-file-name buffer-file-name))))
(require 'ox-latex)

(setq org-latex-compiler "xelatex"
      org-latex-listings t
      org-latex-prefer-user-labels t
      org-latex-image-default-width "\\linewidth"
      org-latex-default-packages-alist
      '(("" "graphicx" t) ("" "longtable" nil) ("" "wrapfig" nil) ("" "rotating" nil)
        ("normalem" "ulem" t) ("" "amsmath" t) ("" "amssymb" t)
        ("" "hyperref" nil))
      org-latex-packages-alist nil
      org-latex-hyperref-template "\\hypersetup{pdfauthor={%a}, pdftitle={%t}, pdfcreator={%c},
  colorlinks=true, linkcolor=notelabel, urlcolor=notelabel, citecolor=notelabel}\n"
      org-latex-classes
      '(("article" "\\documentclass[10pt,a4paper]{article}
\\usepackage[margin=2cm]{geometry}
\\usepackage{fontspec}
\\setmainfont{DejaVu Serif}
\\setsansfont{DejaVu Sans}
\\setmonofont{DejaVu Sans Mono}[Scale=0.95]
\\usepackage{xcolor}
\\usepackage{listings}
\\usepackage{array}
\\usepackage{tabularx}
\\usepackage[font=small,labelfont=bf]{caption}
\\definecolor{notelabel}{HTML}{2a5d8f}
\\definecolor{noterun}{HTML}{1f7a4d}
\\definecolor{noteout}{HTML}{8a6d1f}
\\definecolor{notebg}{HTML}{f6f8fa}
\\lstset{basicstyle=\\ttfamily\\footnotesize, breaklines=true, breakatwhitespace=false,
  columns=fullflexible, keepspaces=true, showstringspaces=false, upquote=true,
  backgroundcolor=\\color{notebg}, frame=none, xleftmargin=0.5em, xrightmargin=0.5em,
  aboveskip=0.4em, belowskip=0.8em,
  keywordstyle=\\color{notelabel}\\bfseries, commentstyle=\\color{gray}\\itshape,
  stringstyle=\\color{noterun}, identifierstyle=\\color{black}, postbreak=\\mbox{\\textcolor{gray}{$\\hookrightarrow$}\\space}}
\\setlength{\\parskip}{0.5em}
\\setlength{\\parindent}{0pt}
\\setlength{\\emergencystretch}{3em}"
         ("\\section{%s}" . "\\section*{%s}")
         ("\\subsection{%s}" . "\\subsection*{%s}")
         ("\\subsubsection{%s}" . "\\subsubsection*{%s}")
         ("\\paragraph{%s}" . "\\paragraph*{%s}"))))

(defun note/latex-label (colour text)
  (format "\\par\\noindent{\\sffamily\\scriptsize\\textcolor{%s}{%s}}\\nopagebreak\n" colour text))

(defun note/latex-escape (text)
  (org-latex--protect-text (org-latex-plain-text text nil)))

(defun note/listing (code size &optional language)
  (let ((lst (cdr (assoc language '(("python" . "Python") ("sh" . "bash") ("bash" . "bash")
                                    ("emacs-lisp" . "Lisp") ("elisp" . "Lisp") ("c" . "C")
                                    ("c++" . "C++") ("sql" . "SQL"))))))
    (format "\\begin{lstlisting}[basicstyle=\\ttfamily%s%s]\n%s\\end{lstlisting}\n"
            size (if lst (concat ",language=" lst) "") code)))

(defun note/latex-src (_orig src-block _contents info)
  (let* ((params (org-element-property :parameters src-block))
         (target (note/param params "tangle"))
         (run (note/param params "run"))
         (code (org-export-format-code-default src-block info))
         (listing (note/listing code "\\footnotesize" (org-element-property :language src-block))))
    (cond
     ((and (stringp target) (not (member target '("no" "yes"))))
      (concat (note/latex-label "notelabel" (concat "$\\rightarrow$ \\texttt{"
                                                    (note/latex-escape (note/relpath target)) "}"))
              listing))
     ((assoc (org-element-property :name src-block) (note/chunks info))
      (concat (note/latex-label "notelabel" (concat "$\\langle$"
                                                    (note/latex-escape (org-element-property :name src-block))
                                                    "$\\rangle$"))
              listing))
     (run (concat (note/latex-label "noterun" (if (stringp run) (format "run (%s)" (note/latex-escape run)) "run"))
                  listing))
     (t listing))))
(advice-add 'org-latex-src-block :around #'note/latex-src)

(defun note/output-size (text)
  "The font size that fits TEXT's widest line on the page: about 100
characters at footnotesize, 114 at scriptsize, 160 at tiny."
  (let ((width (apply #'max 0 (mapcar #'length (split-string text "\n")))))
    (cond ((<= width 100) "\\footnotesize") ((<= width 114) "\\scriptsize") (t "\\tiny"))))

(defun note/latex-example (_orig el _contents info)
  (let* ((code (org-export-format-code-default el info))
         (listing (note/listing code (note/output-size code))))
    (if (note/output-p el info)
        (concat (note/latex-label "noteout" "output") listing)
      listing)))
(advice-add 'org-latex-example-block :around #'note/latex-example)
(advice-add 'org-latex-fixed-width :around #'note/latex-example)

(defun note/latex-frames (orig link info)
  "A figure with frames or a swipe pair: every image, stacked and labelled."
  (let* ((figure (funcall orig link info))
         (attr (org-export-read-attribute :attr_html (org-export-get-parent-element link)))
         (frames (plist-get attr :data-frames))
         (swipe (plist-get attr :data-swipe))
         (images (cond (frames (cons (org-element-property :path link) (split-string frames " " t)))
                       (swipe (cons (org-element-property :path link) (split-string swipe " " t)))))
         (labels (split-string (or (plist-get attr (if frames :data-labels :data-swipe-labels)) "") "|")))
    (if (and images (string-match "\\\\includegraphics\\(\\[[^]]*\\]\\)?{[^}]*}" figure))
        (let ((options (format "[width=\\linewidth,height=%.2f\\textheight,keepaspectratio]"
                               (/ 0.8 (length images))))
              (n -1))
          (replace-match
           (replace-regexp-in-string
            "\\\\" "\\\\\\\\"
            (mapconcat (lambda (image)
                         (setq n (1+ n))
                         (concat (if (nth n labels)
                                     (format "{\\sffamily\\small %s}\\\\[0.2em]\n" (note/latex-escape (nth n labels)))
                                   "")
                                 (format "\\includegraphics%s{%s}" options image)))
                       images "\\\\[0.8em]\n"))
           t nil figure))
      figure)))
(advice-add 'org-latex--inline-image :around #'note/latex-frames)

(defun note/latex-table (orig table contents info)
  "A table wider than the page becomes a tabularx at the line width whose
columns wrap; the widest columns get the most room."
  (let ((latex (funcall orig table contents info))
        (widths nil))
    (org-element-map table 'table-row
      (lambda (row)
        (let ((i 0))
          (org-element-map row 'table-cell
            (lambda (cell)
              (let ((n (length (org-element-interpret-data (org-element-contents cell)))))
                (if (nth i widths) (setcar (nthcdr i widths) (max n (nth i widths)))
                  (setq widths (append widths (list n)))))
              (setq i (1+ i)))))))
    (if (and widths (> (apply #'+ widths) 95)
             (string-match "\\\\begin{tabular}{\\([lcr|]+\\)}" latex))
        (let* ((total (float (apply #'+ widths)))
               (n (length widths))
               (spec (mapconcat (lambda (w)
                                  (format ">{\\raggedright\\arraybackslash\\hsize=%.3f\\hsize}X"
                                          (/ (* n w) total)))
                                widths "")))
          (setq latex (replace-match (concat "\\begin{tabularx}{\\linewidth}{" spec "}") t t latex))
          (replace-regexp-in-string "\\\\end{tabular}" "\\end{tabularx}" latex t t))
      latex)))
(advice-add 'org-latex-table :around #'note/latex-table)

(defun note/export-latex (file)
  (find-file file)
  (message "exported %s" (org-latex-export-to-latex)))

(provide 'export-pdf)
;;; export-pdf.el ends here
