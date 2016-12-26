"""ropemacs, an emacs mode for using rope refactoring library"""
import sys

import ropemode.decorators
import ropemode.environment
import ropemode.interface
from Pymacs import lisp
from rope.base import utils


class LispUtils(ropemode.environment.Environment):

    def ask(self, prompt, default=None, starting=None):
        if default is not None:
            prompt = prompt + ('[%s] ' % default)
        result = lisp.read_from_minibuffer(prompt, starting, None, None,
                                           None, default, None)
        if result == '' and default is not None:
            return default
        return result

    def ask_values(self, prompt, values, default=None, starting=None, exact=True):
        if self._emacs_version() < 22:
            values = [[value, value] for value in values]
        if exact and default is not None:
            prompt = prompt + ('[%s] ' % default)
        reader = lisp['ropemacs-completing-read-function'].value()
        result = reader(prompt, values, None, exact, starting)
        if result == '' and exact:
            return default
        return result

    def ask_completion(self, prompt, values, starting=None):
        return self.ask_values(prompt, values, starting=starting, exact=None)

    def ask_directory(self, prompt, default=None, starting=None):
        location = starting or default
        if location is not None:
            prompt = prompt + ('[%s] ' % location)
        if lisp.fboundp(lisp['read-directory-name']):
            # returns default when starting is entered
            result = lisp.read_directory_name(prompt, location, location)
        else:
            result = lisp.read_file_name(prompt, location, location)
        if result == '' and location is not None:
            return location
        return result

    def message(self, msg):
        message(msg)

    def yes_or_no(self, prompt):
        return lisp.yes_or_no_p(prompt)

    def y_or_n(self, prompt):
        return lisp.y_or_n_p(prompt)

    def get(self, name, default=None):
        lispname = 'ropemacs-' + name.replace('_', '-')
        if lisp.boundp(lisp[lispname]):
            return lisp[lispname].value()
        return default

    def get_offset(self):
        return lisp.point() - 1

    def get_text(self):
        end = lisp.buffer_size() + 1
        old_min = lisp.point_min()
        old_max = lisp.point_max()
        narrowed = (old_min != 1 or old_max != end)
        if narrowed:
            lisp.narrow_to_region(1, lisp.buffer_size() + 1)
        try:
            return lisp.buffer_string()
        finally:
            if narrowed:
                lisp.narrow_to_region(old_min, old_max)

    def get_region(self):
        offset1 = self.get_offset()
        lisp.exchange_point_and_mark()
        offset2 = self.get_offset()
        lisp.exchange_point_and_mark()
        return min(offset1, offset2), max(offset1, offset2)

    def filename(self):
        return lisp.buffer_file_name()

    def is_modified(self):
        return lisp.buffer_modified_p()

    def goto_line(self, lineno):
        lisp.goto_line(lineno)

    def insert_line(self, line, lineno):
        current = lisp.point()
        lisp.goto_line(lineno)
        lisp.insert(line + '\n')
        lisp.goto_char(current + len(line) + 1)

    def insert(self, text):
        lisp.insert(text)

    def delete(self, start, end):
        lisp.delete_region(start, end)

    def filenames(self):
        result = []
        for buffer in lisp.buffer_list():
            filename = lisp.buffer_file_name(buffer)
            if filename:
                result.append(filename)
        return result

    def save_files(self, filenames):
        ask = self.get('confirm_saving')
        initial = lisp.current_buffer()
        for filename in filenames:
            buffer = lisp.find_buffer_visiting(filename)
            if buffer:
                if lisp.buffer_modified_p(buffer):
                    if not ask or lisp.y_or_n_p('Save %s buffer?' % filename):
                        lisp.set_buffer(buffer)
                        lisp.save_buffer()
        lisp.set_buffer(initial)

    def reload_files(self, filenames, moves={}):
        if self.filename() in moves:
            initial = None
        else:
            initial = lisp.current_buffer()
        for filename in filenames:
            buffer = lisp.find_buffer_visiting(filename)
            if buffer:
                if filename in moves:
                    lisp.kill_buffer(buffer)
                    lisp.find_file(moves[filename])
                else:
                    lisp.set_buffer(buffer)
                    lisp.revert_buffer(False, True)
        if initial is not None:
            lisp.set_buffer(initial)

    def find_file(self, filename, readonly=False, other=False):
        if other:
            lisp.find_file_other_window(filename)
        elif readonly:
            lisp.find_file_read_only(filename)
        else:
            lisp.find_file(filename)

    def _make_buffer(self, name, contents, empty_goto=True, switch=False,
                     window='other', modes=[], fit_lines=None):
        """Make an emacs buffer

        `window` can be one of `None`, 'current' or 'other'.
        """
        new_buffer = lisp.get_buffer_create(name)
        lisp.set_buffer(new_buffer)
        lisp.toggle_read_only(-1)
        lisp.erase_buffer()
        if contents or empty_goto:
            lisp.insert(contents)
            for mode in modes:
                lisp[mode + '-mode']()
            lisp.buffer_disable_undo(new_buffer)
            lisp.toggle_read_only(1)
            if switch:
                if window == 'current':
                    lisp.switch_to_buffer(new_buffer)
                else:
                    lisp.switch_to_buffer_other_window(new_buffer)
                lisp.goto_char(lisp.point_min())
            elif window == 'other':
                if self.get("use_pop_to_buffer"):
                    lisp.pop_to_buffer(new_buffer)
                    lisp.goto_char(lisp.point_min())
                else:
                    new_window = lisp.display_buffer(new_buffer)
                    lisp.set_window_point(new_window, lisp.point_min())
                    if (fit_lines
                        and lisp.fboundp(lisp['fit-window-to-buffer'])):
                        lisp.fit_window_to_buffer(new_window, fit_lines)
                        lisp.bury_buffer(new_buffer)
        return new_buffer

    def _hide_buffer(self, name, delete=True):
        buffer = lisp.get_buffer(name)
        if buffer is not None:
            window = lisp.get_buffer_window(buffer)
            if window is not None:
                lisp.bury_buffer(buffer)
                if delete:
                    lisp.delete_window(window)
                else:
                    if lisp.buffer_name(lisp.current_buffer()) == name:
                        lisp.switch_to_buffer(None)

    def _emacs_version(self):
        return int(lisp['emacs-version'].value().split('.')[0])

    def create_progress(self, name):
        if lisp.fboundp(lisp['make-progress-reporter']):
            progress = _LispProgress(name)
        else:
            progress = _OldProgress(name)
        return progress

    def current_word(self):
        return lisp.current_word()

    def push_mark(self):
        marker_ring = self.get('marker_ring')
        marker = lisp.point_marker()
        lisp.ring_insert(marker_ring, marker)

    def pop_mark(self):
        marker_ring = self.get('marker_ring')
        if lisp.ring_empty_p(marker_ring):
            self.message("There are no more marked buffers in \
the rope-marker-ring")
        else:
            oldbuf = lisp.current_buffer()
            marker = lisp.ring_remove(marker_ring, 0)
            marker_buffer = lisp.marker_buffer(marker)
            if marker_buffer is None:
                lisp.message("The marked buffer has been deleted")
                return
            marker_point  = lisp.marker_position(marker)
            lisp.set_buffer(marker_buffer)
            lisp.goto_char(marker_point)
            #Kill that marker so it doesn't slow down editing.
            lisp.set_marker(marker, None, None)
            if not lisp.eq(oldbuf, marker_buffer):
                lisp.switch_to_buffer(marker_buffer)

    def prefix_value(self, prefix):
        return lisp.prefix_numeric_value(prefix)

    def read_line_from_file(self, filename, lineno):
        with open(filename) as f:
            for i, line in enumerate(f):
                if i+1 == lineno:
                    return line

        return "" # If lineno goes beyond the end of the file

    def show_occurrences(self, locations):
        buffer = self._make_buffer('*rope-occurrences*', "", switch=False)
        lisp.set_buffer(buffer)
        lisp.toggle_read_only(0)

        trunc_length = len(lisp.rope_get_project_root())

        lisp.insert('List of occurrences:\n')
        for location in locations:
            code_line = self.read_line_from_file(location.filename, location.lineno).rstrip()
            filename = location.filename[trunc_length:]
            lineno = str(location.lineno)
            offset = str(location.offset)

            lisp.insert(filename + ":" + lineno + ":" + code_line + " " + offset)

            beginning = lisp.line_beginning_position()
            end = beginning + len(filename)

            lisp.add_text_properties(beginning, end, [lisp.face, lisp.button])
            lisp.add_text_properties(beginning, end, [lisp.mouse_face, lisp.highlight,
                                                      lisp.help_echo, "mouse-2: visit this file in other window"])

            lisp.insert("\n")

        lisp.toggle_read_only(1)

        lisp.set(lisp["next-error-function"], lisp.rope_occurrences_next)
        lisp.local_set_key('\r', lisp.rope_occurrences_goto)
        lisp.local_set_key((lisp.mouse_1,), lisp.rope_occurrences_goto)
        lisp.local_set_key('q', lisp.delete_window)


    def show_doc(self, docs, altview=False):
        use_minibuffer = not altview
        if self.get('separate_doc_buffer'):
            use_minibuffer = not use_minibuffer
        if not use_minibuffer:
            fit_lines = self.get('max_doc_buffer_height')
            buffer = self._make_buffer('*rope-pydoc*', docs,
                                       empty_goto=False,
                                       fit_lines=fit_lines)
            lisp.local_set_key('q', lisp.bury_buffer)
        elif docs:
            docs = '\n'.join(docs.split('\n')[:7])
            self.message(docs)

    def preview_changes(self, diffs):
        self._make_buffer('*rope-preview*', diffs, switch=True,
                          modes=['diff'], window='current')
        try:
            return self.yes_or_no('Do the changes? ')
        finally:
            self._hide_buffer('*rope-preview*', delete=False)

    def local_command(self, name, callback, key=None, prefix=False):
        globals()[name] = callback
        self._set_interaction(callback, prefix)
        if self.local_prefix and key:
            key = self._key_sequence(self.local_prefix + ' ' + key)
            self._bind_local(_lisp_name(name), key)

    def _bind_local(self, name, key):
        lisp('(define-key ropemacs-local-keymap "%s" \'%s)' %
             (self._key_sequence(key), name))

    def global_command(self, name, callback, key=None, prefix=False):
        globals()[name] = callback
        self._set_interaction(callback, prefix)
        if self.global_prefix and key:
            key = self._key_sequence(self.global_prefix + ' ' + key)
            lisp.global_set_key(key, lisp[_lisp_name(name)])

    def _key_sequence(self, sequence):
        result = []
        for key in sequence.split():
            if key.startswith('C-'):
                number = ord(key[-1].upper()) - ord('A') + 1
                result.append(chr(number))
            elif key.startswith('M-'):
                number = ord(key[-1].upper()) + 0x80
                result.append(chr(number))
            else:
                result.append(key)
        return ''.join(result)

    def _set_interaction(self, callback, prefix):
        if hasattr(callback, 'im_func'):
            callback = callback.im_func
        if prefix:
            callback.interaction = 'P'
        else:
            callback.interaction = ''

    def add_hook(self, name, callback, hook):
        mapping = {'before_save': 'before-save-hook',
                   'after_save': 'after-save-hook',
                   'exit': 'kill-emacs-hook'}
        globals()[name] = callback
        lisp.add_hook(lisp[mapping[hook]], lisp[_lisp_name(name)])

    @property
    @utils.saveit
    def global_prefix(self):
        return self.get('global_prefix')

    @property
    @utils.saveit
    def local_prefix(self):
        return self.get('local_prefix')


def _lisp_name(name):
    return 'rope-' + name.replace('_', '-')

class _LispProgress(object):

    def __init__(self, name):
        self.progress = lisp.make_progress_reporter('%s ... ' % name, 0, 100)

    def update(self, percent):
        lisp.progress_reporter_update(self.progress, percent)

    def done(self):
        lisp.progress_reporter_done(self.progress)

class _OldProgress(object):

    def __init__(self, name):
        self.name = name
        self.update(0)

    def update(self, percent):
        if percent != 0:
            message('%s ... %s%%%%' % (self.name, percent))
        else:
            message('%s ... ' % self.name)

    def done(self):
        message('%s ... done' % self.name)


def message(message):
    lisp.message(message.replace('%', '%%'))

def occurrences_goto():
    if lisp.line_number_at_pos() < 1:
        lisp.forward_line(1 - lisp.line_number_at_pos())
    lisp.end_of_line()
    end = lisp.point()
    lisp.beginning_of_line()
    line = lisp.buffer_substring_no_properties(lisp.point(), end)
    tokens = line.split()
    semicolon_tokens = line.split(":")

    project_root = lisp.rope_get_project_root()
    if tokens and semicolon_tokens:
        # Mark this line with an arrow
        lisp('''
        (remove-overlays (point-min) (point-max))
            (overlay-put (make-overlay (line-beginning-position) (line-end-position))
            'before-string
            (propertize "A" 'display '(left-fringe right-triangle)))
        ''')


        filename = project_root + "/" + semicolon_tokens[0]
        offset = int(tokens[-1])
        resource = _interface._get_resource(filename)
        LispUtils().find_file(resource.real_path, other=True)
        lisp.goto_char(offset + 1)
occurrences_goto.interaction = ''

def occurrences_next(arg, reset):
    lisp.switch_to_buffer_other_window('*rope-occurrences*', True)
    if reset:
        lisp.goto_char(lisp.point_min())
    lisp.forward_line(arg)
    if lisp.eobp():
        lisp.message("Cycling rope occurences")
        lisp.goto_char(lisp.point_min())
    occurrences_goto()
occurrences_next.interaction = ''


DEFVARS = """\
(defgroup ropemacs nil
  "ropemacs, an emacs plugin for rope."
  :link '(url-link "http://rope.sourceforge.net/ropemacs.html")
  :prefix "rope-")

(defcustom ropemacs-confirm-saving t
  "Shows whether to confirm saving modified buffers before refactorings.

If non-nil, you have to confirm saving all modified
python files before refactorings; otherwise they are
saved automatically.")

(defcustom ropemacs-codeassist-maxfixes 1
  "The number of errors to fix before code-assist.

How many errors to fix, at most, when proposing code completions.")

(defcustom ropemacs-codeassist-noerror nil
  "Ignore errors in the code during code-assist if it is non-nil.")

(defcustom ropemacs-separate-doc-buffer t
  "Should `rope-show-doc' use a separate buffer or the minibuffer.")
(defcustom ropemacs-max-doc-buffer-height 22
  "The maximum buffer height for `rope-show-doc'.")

(defcustom ropemacs-use-pop-to-buffer nil
  "Use native `pop-to-buffer' to show new buffer.

This affect all ropemacs function including `rope-show-doc'.")

(defcustom ropemacs-enable-autoimport 'nil
  "Specifies whether autoimport should be enabled.")
(defcustom ropemacs-autoimport-modules nil
  "The name of modules whose global names should be cached.

The `rope-generate-autoimport-cache' reads this list and fills its
cache.")
(defcustom ropemacs-autoimport-underlineds 'nil
  "If set, autoimport will cache names starting with underlines, too.")

(defcustom ropemacs-completing-read-function (if (and (boundp 'ido-mode)
                                                      ido-mode)
                                                 'ido-completing-read
                                               'completing-read)
  "Function to call when prompting user to choose between a list of options.
This should take the same arguments as `completing-read'.
Possible values are `completing-read' and `ido-completing-read'.
Note that you must set `ido-mode' if using`ido-completing-read'."
  :type 'function)

(make-obsolete-variable
  'rope-confirm-saving 'ropemacs-confirm-saving)
(make-obsolete-variable
  'rope-code-assist-max-fixes 'ropemacs-codeassist-maxfixes)

(defcustom ropemacs-local-prefix "C-c r"
  "The prefix for ropemacs refactorings.

Use nil to prevent binding keys.")

(defcustom ropemacs-global-prefix "C-x p"
  "The prefix for ropemacs project commands.

Use nil to prevent binding keys.")

(defcustom ropemacs-marker-ring-length 16
  "Length of the rope marker ring.")

(defcustom ropemacs-marker-ring (make-ring ropemacs-marker-ring-length)
  "Ring of markers which are locations from which goto-definition was invoked.")

(defcustom ropemacs-enable-shortcuts 't
  "Shows whether to bind ropemacs shortcuts keys.

If non-nil it binds:

================  ============================
Key               Command
================  ============================
M-/               rope-code-assist
C-c g             rope-goto-definition
C-c u             rope-pop-mark
C-c d             rope-show-doc
C-c f             rope-find-occurrences
M-?               rope-lucky-assist
================  ============================
")

(defvar ropemacs-local-keymap (make-sparse-keymap))

(easy-menu-define ropemacs-mode-menu ropemacs-local-keymap
"`ropemacs' menu"
                  '("Rope"
                    ["Code assist" rope-code-assist t]
                    ["Lucky assist" rope-lucky-assist t]
                    ["Goto definition" rope-goto-definition t]
                    ["Pop mark" rope-pop-mark t]
                    ["Jump to global" rope-jump-to-global t]
                    ["Show documentation" rope-show-doc t]
                    ["Find Occurrences" rope-find-occurrences t]
                    ["Analyze module" rope-analyze-module t]
                    ("Refactor"
                      ["Inline" rope-inline t]
                      ["Extract Variable" rope-extract-variable t]
                      ["Extract Method" rope-extract-method t]
                      ["Organize Imports" rope-organize-imports t]
                      ["Rename" rope-rename t]
                      ["Move" rope-move t]
                      ["Restructure" rope-restructure t]
                      ["Use Function" rope-use-function t]
                      ["Introduce Factory" rope-introduce-factory t]
                      ("Generate"
                        ["Class" rope-generate-class t]
                        ["Function" rope-generate-function t]
                        ["Module" rope-generate-module t]
                        ["Package" rope-generate-package t]
                        ["Variable" rope-generate-variable t]
                      )
                      ("Module"
                        ["Module to Package" rope-module-to-package t]
                        ["Rename Module" rope-rename-current-module t]
                        ["Move Module" rope-move-current-module t]
                      )
                      "--"
                      ["Undo" rope-undo t]
                      ["Redo" rope-redo t]
                    )
                    ("Project"
                      ["Open project" rope-open-project t]
                      ["Close project" rope-close-project t]
                      ["Find file" rope-find-file t]
                      ["Open project config" rope-project-config t]
                    )
                    ("Create"
                      ["Module" rope-create-module t]
                      ["Package" rope-create-package t]
                      ["File" rope-create-file t]
                      ["Directory" rope-create-directory t]
                    )
                    ))

(defcustom ropemacs-guess-project 'nil
  "Try to guess the project when needed.

If non-nil, ropemacs tries to guess and open the project that contains
a file on which the rope command is performed when no project is
already opened.")

(provide 'ropemacs)
"""

MINOR_MODE = """\
(require 'thingatpt)

(define-minor-mode ropemacs-mode
 "ropemacs, rope in emacs!" nil " Rope" ropemacs-local-keymap
  (if ropemacs-mode
      (add-hook 'completion-at-point-functions 'ropemacs-completion-at-point nil t)
    (remove-hook 'completion-at-point-functions 'ropemacs-completion-at-point t)))

(defun ropemacs-completion-at-point ()
  (unless (nth 8 (syntax-ppss))
    (let ((bounds (or (bounds-of-thing-at-point 'symbol)
                      (cons (point) (point)))))
      (list (car bounds)
            (cdr bounds)
            'ropemacs--completion-table
            :company-doc-buffer 'ropemacs--completion-doc-buffer
            :company-location 'ropemacs--completion-location))))

(defalias 'ropemacs--completion-table
  (if (fboundp 'completion-table-with-cache)
      (completion-table-with-cache #'ropemacs--completion-candidates)
    (completion-table-dynamic #'ropemacs--completion-candidates)))

(defun ropemacs--completion-candidates (prefix)
  (mapcar (lambda (element) (concat prefix element))
          (rope-completions)))

(defun ropemacs--with-inserted (candidate fn)
  (let ((inhibit-modification-hooks t)
        (inhibit-point-motion-hooks t)
        (modified-p (buffer-modified-p))
        (beg (or (car (bounds-of-thing-at-point 'symbol)) (point)))
        (pt (point)))
     (insert (substring candidate (- pt beg)))
     (unwind-protect
         (funcall fn)
       (delete-region pt (point))
       (set-buffer-modified-p modified-p))))

(defun ropemacs--completion-doc-buffer (candidate)
  (let ((doc (ropemacs--with-inserted candidate #'rope-get-doc)))
    (when doc
      (with-current-buffer (get-buffer-create "*ropemacs-completion-doc*")
        (erase-buffer)
        (insert doc)
        (goto-char (point-min))
        (current-buffer)))))

(defun ropemacs--completion-location (candidate)
  (let ((location (ropemacs--with-inserted
                   candidate #'rope-definition-location)))
    (when location
      (cons (elt location 0) (elt location 1)))))
"""

shortcuts = [('M-/', 'rope-code-assist'),
             ('M-?', 'rope-lucky-assist'),
             ('C-c g', 'rope-goto-definition'),
             ('C-c u', 'rope-pop-mark'),
             ('C-c d', 'rope-show-doc'),
             ('C-c f', 'rope-find-occurrences')]


_interface = None

def _load_ropemacs():
    global _interface
    ropemode.decorators.logger.message = message
    lisp(DEFVARS)
    _interface = ropemode.interface.RopeMode(env=LispUtils())
    _interface.init()
    lisp(MINOR_MODE)

    if LispUtils().get('enable_shortcuts'):
        for key, command in shortcuts:
            LispUtils()._bind_local(command, key)

    lisp.add_hook(lisp['python-mode-hook'], lisp['ropemacs-mode'])

def _started_from_pymacs():
    import inspect
    frame = sys._getframe()
    while frame:
        # checking frame.f_code.co_name == 'pymacs_load_helper' might
        # be very fragile.
        filename = inspect.getfile(frame).rstrip('c')
        if filename.endswith(('Pymacs.py', 'pymacs.py')):
            return True
        frame = frame.f_back

if _started_from_pymacs():
    _load_ropemacs()
