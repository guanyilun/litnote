;;; export-note.el --- batch org -> html for org notes  -*- lexical-binding: t -*-
;;
;; Used by mk/litnote.mk; not meant to be loaded interactively.
;;
;;   emacs -Q --batch -l $LITNOTE/lisp/export-note.el \
;;         --eval '(note/export-html "notes/x.org")'
;;
;; The one setting that matters: `org-export-use-babel' is nil.
;;
;; At the default t, babel pre-processes the buffer during export and strips
;; the #+RESULTS: of every block whose :exports is `code' -- which is the
;; default, and what these notes use.  A plain `C-c C-e h h' therefore
;; drops every figure and output block, leaving source code and prose only.
;; Setting this to nil skips babel export processing entirely, so the results
;; already in the buffer are exported as ordinary content.
;;
;; The alternative -- `:exports both' on every block -- keeps the results but
;; re-runs the code at export time, which can mean reloading all the data.  Exporting should render what was computed, not recompute it.
;;
;; Source blocks come out as plain <pre> here (htmlize.el is not installed);
;; py/highlight-html.py colours them afterwards with pygments.

(require 'org)
(require 'ox-html)

(setq org-export-use-babel nil
      org-confirm-babel-evaluate nil
      make-backup-files nil
      vc-handled-backends nil
      org-export-with-toc t
      org-export-with-section-numbers t
      org-export-with-smart-quotes t)

(defconst note/html-css "
<style>
  html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }
  body { margin: 0; padding: 0;
         font-family: Charter, Georgia, 'Times New Roman', serif;
         font-size: 17px; line-height: 1.6; color: #1a1a1a;
         transition: padding-left .18s ease; }
  #content { max-width: 62rem; margin: 2rem auto; padding: 0 1.25rem 4rem; }
  /* org puts the author/date footer outside #content, so it misses the
     centering and sits against the window edge under the sidebar layout. */
  #postamble { max-width: 62rem; margin: 0 auto 3rem; padding: 1rem 1.25rem 0;
               border-top: 1px solid #d8d8d8; color: #6a6a6a;
               font-size: .85rem; }
  #postamble p { margin: .2rem 0; }
  h1 { font-size: 1.9rem; line-height: 1.25; }
  h2 { font-size: 1.4rem; margin-top: 2.4rem; padding-bottom: .25rem;
       border-bottom: 1px solid #d8d8d8; }
  h3 { font-size: 1.12rem; margin-top: 1.8rem; color: #333; }
  h2, h3, h4 { scroll-margin-top: 1rem; }
  a { color: #1a5fb4; }
  code, pre { font-family: 'DejaVu Sans Mono', Menlo, Consolas, monospace; }
  code { font-size: .88em; background: #f2f2f2; padding: .1em .3em;
         border-radius: 3px; }
  pre.src, pre.example {
      font-size: .82rem; line-height: 1.45; overflow-x: auto;
      padding: .8rem 1rem; border-radius: 5px; }
  /* code the reader runs */
  pre.src { background: #f7f7f4; border: 1px solid #e0e0da;
            border-left: 3px solid #7a9e7e; }
  /* output the code produced */
  pre.example { background: #fbfaf7; border: 1px solid #e6e2d8;
                border-left: 3px solid #c8a45c; color: #333; }
  figure, p > img { margin: 1.6rem 0; text-align: center; }
  figcaption { text-align: left; font-size: .9rem; line-height: 1.45; color: #444;
               margin: .5rem auto 0; max-width: 46rem; }
  figcaption .figure-number { font-weight: bold; color: #222; }
  .frame-bar { margin: .35rem 0 0; font: .8rem/1.3 'DejaVu Sans Mono', monospace; color: #555; }
  .frame-bar button { font: inherit; padding: .1rem .5rem; margin: 0 .5rem; cursor: pointer;
      border: 1px solid #ccc; border-radius: 4px; background: #fff; color: #333; }
  .frame-bar button:hover { background: #f0f0f0; }
  img { max-width: 100%; height: auto; border: 1px solid #e5e5e5;
        border-radius: 4px; background: #fff; }
  table { border-collapse: collapse; font-size: .92rem; margin: 1.2rem 0; }
  th, td { border: 1px solid #ddd; padding: .35rem .6rem; }
  th { background: #f2f2f2; }
  .title { text-align: left; margin-bottom: .2rem; }
  .subtitle, .author, .date { color: #666; font-size: .95rem; }
  blockquote { border-left: 3px solid #ccc; margin-left: 0;
               padding-left: 1rem; color: #444; }

  /* --- table of contents as a collapsible sidebar ------------------- */
  #table-of-contents {
      position: fixed; top: 0; left: 0; bottom: 0; width: 20rem;
      overflow-y: auto; overscroll-behavior: contain; z-index: 20;
      background: #fafafa; border-right: 1px solid #e5e5e5;
      padding: 3.1rem 1rem 2rem; font-size: .88rem; line-height: 1.45;
      transform: translateX(-100%); transition: transform .18s ease; }
  body.toc-open #table-of-contents { transform: none; }
  body.toc-open { padding-left: 20rem; }
  #table-of-contents h2 { border: 0; margin: 0 0 .6rem; font-size: .8rem;
      text-transform: uppercase; letter-spacing: .06em; color: #888;
      font-family: inherit; }
  #table-of-contents ul { list-style: none; margin: 0; padding-left: .7rem; }
  #table-of-contents > #text-table-of-contents > ul { padding-left: 0; }
  #table-of-contents li { margin: .12rem 0; }
  #table-of-contents a { display: block; text-decoration: none; color: #444;
      padding: .18rem .4rem; border-left: 2px solid transparent;
      border-radius: 0 3px 3px 0; }
  #table-of-contents a:hover { background: #ececec; color: #1a5fb4; }
  #table-of-contents a.toc-active { color: #1a5fb4; font-weight: 600;
      border-left-color: #1a5fb4; background: #eef3fb; }
  #toc-toggle { position: fixed; top: .55rem; left: .55rem; z-index: 30;
      width: 2.1rem; height: 2.1rem; padding: 0; cursor: pointer;
      font: 1rem/1 'DejaVu Sans Mono', monospace; color: #444;
      background: #fff; border: 1px solid #dcdcdc; border-radius: 5px; }
  #toc-toggle:hover { background: #f0f0f0; }

  /* narrow: overlay instead of pushing the text over */
  @media (max-width: 70rem) {
    body.toc-open { padding-left: 0; }
    body.toc-open #content::after { content: ''; position: fixed; inset: 0;
        background: rgba(0,0,0,.28); z-index: 15; }
  }
  @media print { #toc-toggle { display: none; }
                 #table-of-contents { position: static; transform: none;
                                      width: auto; border: 0; } }

  /* --- foldable sections -------------------------------------------- */
  .outline-2 > h2, .outline-3 > h3, .outline-4 > h4, .outline-5 > h5 {
      cursor: pointer; position: relative; }
  .outline-2 > h2::before, .outline-3 > h3::before,
  .outline-4 > h4::before, .outline-5 > h5::before {
      content: '\u25BE'; position: absolute; left: -.95em; top: .2em;
      font-size: .72em; color: #b4b4b4; transition: transform .15s ease; }
  .folded > h2::before, .folded > h3::before,
  .folded > h4::before, .folded > h5::before { transform: rotate(-90deg); }
  /* the heading is always the container's first child */
  .folded > *:not(:first-child) { display: none; }
  .folded > h2, .folded > h3, .folded > h4 { opacity: .78; }
  #fold-toggle { position: fixed; top: .55rem; left: 3.05rem; z-index: 30;
      width: 2.1rem; height: 2.1rem; padding: 0; cursor: pointer;
      font: .95rem/1 'DejaVu Sans Mono', monospace; color: #444;
      background: #fff; border: 1px solid #dcdcdc; border-radius: 5px; }
  #fold-toggle:hover { background: #f0f0f0; }
  @media print { .folded > *:not(:first-child) { display: revert !important; }
                 #fold-toggle { display: none; } }

  /* --- notebook cells: tangled code, run, output ----------------------- */
  .cell-label { margin: 1.1rem 0 -.55rem; font: .78rem/1.3 'DejaVu Sans Mono', monospace;
      color: #6a6a6a; }
  .cell-label code { background: #eef3f8; color: #2a5d8f; padding: .1rem .4rem;
      border-radius: 3px; }
  .cell-label.run { color: #1f7a4d; font-weight: bold; }
  .cell-label.output { color: #8a6d1f; margin-top: .2rem; }
  .cell-label.chunk a { color: #2a5d8f; text-decoration: none; }
  .cell-label.chunk a:hover { text-decoration: underline; }
  pre.src a.chunk-ref { color: inherit; text-decoration: underline dotted; }
  .run-cell pre.src { background: #f1f8f3; border-color: #cfe6d7; }
  .output-cell pre.example { border-left: 3px solid #d9c27a; }
  /* Outputs are folded by default; the label stays visible above them. */
  details.output-cell > summary { cursor: pointer; margin: .65rem 0 .2rem;
      font: .78rem/1.3 'DejaVu Sans Mono', monospace; color: #8a6d1f; }
  details.output-cell > summary:hover { text-decoration: underline; }
  details.output-cell[open] > summary { margin-bottom: 0; }

  @media (prefers-color-scheme: dark) {
    .cell-label { color: #8a8a8a; }
    .cell-label code { background: #1f2a36; color: #8cb4e0; }
    .cell-label.run { color: #6fc596; }
    .cell-label.output { color: #d2b460; }
    .cell-label.chunk a { color: #8cb4e0; }
    .run-cell pre.src { background: #18231c; border-color: #2c4235; }
    .output-cell pre.example { border-left-color: #7d6a2f; }
    details.output-cell > summary { color: #d2b460; }
    body { background: #16181c; color: #dcdcdc; }
    h3 { color: #c8c8c8; }
    a { color: #7aa7e0; }
    code { background: #24272c; }
    pre.src { background: #1c1f24; border-color: #2c3037; }
    pre.example { background: #1a1d21; border-color: #2c3037; color: #c8c8c8; }
    th, td { border-color: #333; } th { background: #24272c; }
    img { border-color: #333; }
    figcaption { color: #bbb; }
    figcaption .figure-number { color: #ddd; }
    #postamble { border-top-color: #2c3037; color: #8a8a8a; }
    #table-of-contents { background: #1a1d21; border-right-color: #2c3037; }
    #table-of-contents a { color: #b8b8b8; }
    #table-of-contents a:hover { background: #24272c; color: #7aa7e0; }
    #table-of-contents a.toc-active { color: #7aa7e0; background: #1f2530;
        border-left-color: #7aa7e0; }
    #toc-toggle, #fold-toggle { background: #24272c; border-color: #3a3f47;
        color: #ccc; }
    #toc-toggle:hover, #fold-toggle:hover { background: #2f333a; }
    .outline-2 > h2::before, .outline-3 > h3::before,
    .outline-4 > h4::before, .outline-5 > h5::before { color: #6a6a6a; }
  }
</style>")

(defconst note/html-js "
<script>
document.addEventListener('DOMContentLoaded', function () {
  var toc = document.getElementById('table-of-contents');
  if (!toc) return;

  var btn = document.createElement('button');
  btn.id = 'toc-toggle';
  btn.type = 'button';
  btn.textContent = '\\u2630';
  btn.title = 'Toggle contents';
  btn.setAttribute('aria-label', 'Toggle table of contents');
  btn.setAttribute('aria-controls', 'table-of-contents');
  document.body.appendChild(btn);

  var KEY = 'note-toc-open';
  var wide = function () {
    return window.matchMedia('(min-width: 70rem)').matches;
  };
  var open = false;
  function setOpen(o) {
    open = o;
    document.body.classList.toggle('toc-open', o);
    btn.setAttribute('aria-expanded', o ? 'true' : 'false');
    try { localStorage.setItem(KEY, o ? '1' : '0'); } catch (e) {}
  }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  // Open by default on a wide screen, closed on a narrow one.
  setOpen(saved === null ? wide() : saved === '1');

  btn.addEventListener('click', function () { setOpen(!open); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && open && !wide()) setOpen(false);
  });


  // --- foldable sections ------------------------------------------------
  // org nests each section as <div class=\"outline-N\"><hN>..</hN> rest </div>,
  // so folding is just hiding every child after the heading.
  var conts = document.querySelectorAll('#content div[class^=\"outline-\"]');
  function headOf(c) {
    var h = c.firstElementChild;
    return (h && /^H[2-6]$/.test(h.tagName)) ? h : null;
  }
  conts.forEach(function (c) {
    if (!headOf(c)) return;
    headOf(c).addEventListener('click', function (e) {
      if (e.target.closest('a')) return;          // leave links in headings alone
      if (window.getSelection().toString()) return;   // don't fold on text select
      c.classList.toggle('folded');
    });
  });

  var fbtn = document.createElement('button');
  fbtn.id = 'fold-toggle';
  fbtn.type = 'button';
  fbtn.textContent = '\u00B1';
  fbtn.title = 'Fold / unfold all sections';
  fbtn.setAttribute('aria-label', 'Fold or unfold all sections');
  document.body.appendChild(fbtn);
  fbtn.addEventListener('click', function () {
    var anyOpen = Array.prototype.some.call(conts, function (c) {
      return headOf(c) && !c.classList.contains('folded');
    });
    conts.forEach(function (c) {
      if (headOf(c)) c.classList.toggle('folded', anyOpen);
    });
    if (!anyOpen) window.scrollTo({ top: 0 });
  });

  // Folded outputs are opened for printing, and folded back afterwards.
  var printed = [];
  window.addEventListener('beforeprint', function () {
    printed = Array.prototype.filter.call(document.querySelectorAll('details.output-cell'),
                                          function (d) { return !d.open; });
    printed.forEach(function (d) { d.open = true; });
  });
  window.addEventListener('afterprint', function () {
    printed.forEach(function (d) { d.open = false; });
    printed = [];
  });

  // A target inside a folded section has to be revealed, or the link goes
  // nowhere visible.
  function reveal(id) {
    var el = document.getElementById(id);
    for (var n = el; n && n !== document.body; n = n.parentNode) {
      if (n.classList) n.classList.remove('folded');
    }
    return el;
  }
  window.addEventListener('hashchange', function () {
    var el = reveal(decodeURIComponent(location.hash.slice(1)));
    if (el) el.scrollIntoView();
  });
  if (location.hash) reveal(decodeURIComponent(location.hash.slice(1)));

  var links = [], targets = [];
  toc.querySelectorAll('a[href^=\\\"#\\\"]').forEach(function (a) {
    var el = document.getElementById(a.getAttribute('href').slice(1));
    if (el) { links.push(a); targets.push(el); }
    // On a narrow screen the sidebar overlays the text, so get out of the way.
    a.addEventListener('click', function () {
      reveal(a.getAttribute('href').slice(1));
      if (!wide()) setOpen(false);
    });
  });
  if (!targets.length) return;

  // Highlight the deepest heading above the top of the viewport.  A plain
  // scroll handler beats IntersectionObserver here: several headings are
  // visible at once in a long note, and the observer flickers between them.
  var active = null, queued = false;
  function spy() {
    queued = false;
    var y = window.scrollY + 100, cur = 0;
    for (var i = 0; i < targets.length; i++) {
      if (targets[i].getBoundingClientRect().top + window.scrollY <= y) cur = i;
    }
    if (cur === active) return;
    if (active !== null) links[active].classList.remove('toc-active');
    links[cur].classList.add('toc-active');
    active = cur;
    var a = links[cur], box = toc.getBoundingClientRect();
    var r = a.getBoundingClientRect();
    if (r.top < box.top || r.bottom > box.bottom) {
      a.scrollIntoView({ block: 'nearest' });
    }
  }
  window.addEventListener('scroll', function () {
    if (!queued) { queued = true; requestAnimationFrame(spy); }
  }, { passive: true });
  spy();
});

// Figures with frames: an <img data-frames='a.png b.png'> has extra frames
// (inlined by inline-images.py as data URIs joined by |) and optional
// data-labels, one per frame, the image itself first.  j / k step the
// figure nearest the middle of the screen; the buttons under it too.
document.addEventListener('DOMContentLoaded', function () {
  var figs = Array.prototype.map.call(document.querySelectorAll('img[data-frames]'), function (img) {
    var raw = img.getAttribute('data-frames');
    var srcs = raw.indexOf('data:') === 0 ? raw.split('|') : raw.split(' ').filter(Boolean);
    srcs.unshift(img.getAttribute('src'));
    var labels = (img.getAttribute('data-labels') || '').split('|');
    var bar = document.createElement('div');
    bar.className = 'frame-bar';
    bar.innerHTML = '<button type=button class=frame-prev>&#8249; k</button>' +
      '<span class=frame-label></span><button type=button class=frame-next>j &#8250;</button>';
    img.insertAdjacentElement('afterend', bar);
    var f = { img: img, srcs: srcs, labels: labels, i: 0, bar: bar };
    f.show = function (i) {
      f.i = (i + f.srcs.length) % f.srcs.length;
      f.img.src = f.srcs[f.i];
      bar.querySelector('.frame-label').textContent = 'frame ' + (f.i + 1) + ' of ' + f.srcs.length +
        (f.labels[f.i] ? ': ' + f.labels[f.i] : '');
    };
    bar.querySelector('.frame-prev').onclick = function () { f.show(f.i - 1); };
    bar.querySelector('.frame-next').onclick = function () { f.show(f.i + 1); };
    f.show(0);
    return f;
  });
  if (!figs.length) return;
  function current() {
    var mid = window.innerHeight / 2, best = null, bd = Infinity;
    figs.forEach(function (f) {
      var r = f.img.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight) return;
      var d = Math.abs((r.top + r.bottom) / 2 - mid);
      if (d < bd) { bd = d; best = f; }
    });
    return best;
  }
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (e.key !== 'j' && e.key !== 'k') return;
    var f = current();
    if (!f) return;
    f.show(f.i + (e.key === 'j' ? 1 : -1));
    e.preventDefault();
  });
});
</script>")

;; Notebook reading of the export.  Four kinds of block, each labelled:
;;   - a block with :tangle FILE is code that becomes FILE ("-> FILE");
;;   - a named block that a :noweb outline includes as <<name>> is a piece of
;;     that outline's file ("<name> in -> FILE"); py/highlight-html.py turns
;;     each <<name>> in the outline into a link to it, and the name in the
;;     label links back;
;;   - a block with :run is a cell that was executed, as a script, a slurm job
;;     or a shell command -- its body is the command ("run");
;;   - an example / fixed-width block right after a :run cell, or saved as the
;;     #+RESULTS: of an evaluated block, is that cell's output ("output").
;; Paths are shown relative to the project root (the directory above notes/).
(defun note/param (params key)
  (and params (string-match (concat ":" key "\\(?:[ \t]+\\([^ \t\n:][^ \t\n]*\\)\\)?") params)
       (or (match-string 1 params) t)))

(defun note/relpath (target)
  (let* ((dir (file-name-directory (or (buffer-file-name) default-directory)))
         (root (file-name-directory (directory-file-name dir)))
         (abs (expand-file-name target dir)))
    (if (string-prefix-p root abs) (file-relative-name abs root) target)))

(defun note/slug (name)
  (string-trim (replace-regexp-in-string "[^a-z0-9]+" "-" (downcase name)) "-+" "-+"))

(defvar note/chunks-cache nil)

(defun note/chunks (info)
  "Alist of the blocks that :noweb outlines include: (NAME . FILE).
FILE is the :tangle target the outline, or the chain of outlines, ends in."
  (let ((tree (plist-get info :parse-tree)))
    (unless (eq (car note/chunks-cache) tree)
      (let (parent)
        (org-element-map tree 'src-block
          (lambda (b)
            (let* ((params (org-element-property :parameters b))
                   (noweb (note/param params "noweb"))
                   (target (note/param params "tangle"))
                   (file (and (stringp target) (not (member target '("no" "yes"))) target))
                   (name (org-element-property :name b))
                   (value (org-element-property :value b))
                   (start 0))
              (when (and (stringp noweb) (not (equal noweb "no")))
                (while (string-match "<<\\([^\n<>]+?\\)>>" value start)
                  (push (cons (match-string 1 value) (if file (list 'file file) (list 'chunk name)))
                        parent)
                  (setq start (match-end 0)))))))
        (setq note/chunks-cache
              (cons tree
                    (mapcar (lambda (p)
                              (let ((up (cdr p)) (n 0))
                                (while (and (eq (car up) 'chunk) (< n 20))
                                  (setq up (cdr (assoc (cadr up) parent)) n (1+ n)))
                                (cons (car p) (and (eq (car up) 'file) (cadr up)))))
                            parent)))))
    (cdr note/chunks-cache)))

(defun note/label (cls text)
  (format "<div class=\"cell-label %s\">%s</div>\n" cls text))

(defun note/src-label (orig src-block contents info)
  (let* ((params (org-element-property :parameters src-block))
         (target (note/param params "tangle"))
         (run (note/param params "run"))
         (html (funcall orig src-block contents info)))
    (cond
     ((and (stringp target) (not (member target '("no" "yes"))))
      (concat (note/label "tangle" (format "&#8594; <code>%s</code>"
                                           (org-html-encode-plain-text (note/relpath target))))
              html))
     ((assoc (org-element-property :name src-block) (note/chunks info))
      (let* ((name (org-element-property :name src-block))
             (file (cdr (assoc name (note/chunks info))))
             (slug (note/slug name)))
        (concat (format "<div class=\"cell-label chunk\" id=\"chunk-%s\"><a href=\"#use-%s\">&#10216;%s&#10217;</a>%s</div>\n"
                        slug slug (org-html-encode-plain-text name)
                        (if file (format " in &#8594; <code>%s</code>"
                                         (org-html-encode-plain-text (note/relpath file)))
                          ""))
                html)))
     (run
      (concat (note/label "run" (if (stringp run)
                                    (format "&#9654; run (%s)" (org-html-encode-plain-text run))
                                  "&#9654; run"))
              "<div class=\"run-cell\">" html "</div>"))
     (t html))))
(advice-add 'org-html-src-block :around #'note/src-label)

(defun note/output-p (el info)
  (or (org-element-property :results el)
      (let ((prev (org-export-get-previous-element el info)))
        (and prev (eq (org-element-type prev) 'src-block)
             (note/param (org-element-property :parameters prev) "run")))))

(defun note/output-label (orig el contents info)
  (let ((html (funcall orig el contents info)))
    (if (note/output-p el info)
        (let ((n (length (split-string (or (org-element-property :value el) "") "\n" t))))
          (concat (note/label "output" "output")
                  "<details class=\"output-cell\"><summary>"
                  (format "%d line%s" n (if (= n 1) "" "s"))
                  "</summary>" html "</details>"))
      html)))
(advice-add 'org-html-example-block :around #'note/output-label)
(advice-add 'org-html-fixed-width :around #'note/output-label)

;; The review-comment layer (lisp/review-comments.html: CSS + JS, kept in
;; its own file so it need not be escaped into an elisp string).  Comments
;; live in the reader's browser and are exported as an org file.
(defconst note/review-comments
  (with-temp-buffer
    (insert-file-contents (expand-file-name "review-comments.html"
                                            (file-name-directory (or load-file-name buffer-file-name))))
    (buffer-string)))

(defun note/export-html (file)
  (setq org-html-validation-link nil
        org-html-doctype "html5"
        org-html-html5-fancy t
        org-html-head-include-default-style nil
        org-html-head-extra (concat note/html-css note/html-js note/review-comments))
  ;; MathJax 3 rather than org's default 2.7: 2.7's HTML-CSS output takes the
  ;; page's serif font, leaving variables upright and accents misplaced.
  ;; Loaded from jsDelivr, so equations need network access to render.
  (setq org-html-mathjax-template
        "<script>window.MathJax = { tex: { tags: 'ams' }, chtml: { scale: 1.0 } };</script>
<script id=\"MathJax-script\" async src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js\"></script>")
  (find-file file)
  (message "exported %s" (org-html-export-to-html)))

(provide 'export-note)
;;; export-note.el ends here
