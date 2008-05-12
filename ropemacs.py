"""ropemacs, an emacs mode for using rope refactoring library"""
from Pymacs import lisp
from rope.base import taskhandle

import ropecommon.dialog
import ropecommon.interface


class LispUtils(object):

    def get(self, name):
        return lisp[name].value()

    def yes_or_no(self, prompt):
        return lisp.yes_or_no_p(prompt)

    def y_or_n(self, prompt):
        return lisp.y_or_n_p(prompt)

    def get_region(self):
        offset1 = self.get_offset()
        lisp.exchange_point_and_mark()
        offset2 = self.get_offset()
        lisp.exchange_point_and_mark()
        return min(offset1, offset2), max(offset1, offset2)

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

    def save_files(self, filenames, ask=False):
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

    def make_buffer(self, name, contents, empty_goto=True, switch=False,
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
                new_window = lisp.display_buffer(new_buffer)
                lisp.set_window_point(new_window, lisp.point_min())
                if fit_lines and lisp.fboundp(lisp['fit-window-to-buffer']):
                    lisp.fit_window_to_buffer(new_window, fit_lines)
                    lisp.bury_buffer(new_buffer)
        return new_buffer


    def hide_buffer(self, name, delete=True):
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


    def message(self, message):
        lisp.message(message)


    def askdata(self, data, starting=None):
        """`data` is a `ropecommon.dialog.Data` object"""
        ask_func = self.ask
        ask_args = {'prompt': data.prompt, 'starting': starting,
                    'default': data.default}
        if data.values:
            ask_func = self.ask_values
            ask_args['values'] = data.values
        elif data.kind == 'directory':
            ask_func = self.ask_directory
        return ask_func(**ask_args)


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


    def ask(self, prompt, default=None, starting=None):
        if default is not None:
            prompt = prompt + ('[%s] ' % default)
        result = lisp.read_from_minibuffer(prompt, starting, None, None,
                                           None, default, None)
        if result == '' and default is not None:
            return default
        return result

    def ask_directory(self, prompt, default=None, starting=None):
        if default is not None:
            prompt = prompt + ('[%s] ' % default)
        if lisp.fboundp(lisp['read-directory-name']):
            result = lisp.read_directory_name(prompt, starting, default)
        else:
            result = lisp.read_file_name(prompt, starting, default)
        if result == '' and default is not None:
            return default
        return result

    def _emacs_version(self):
        return int(lisp['emacs-version'].value().split('.')[0])

    def runtask(self, command, name, interrupts=True):
        return RunTask(command, name, interrupts)()

    def create_progress(self, name):
        if lisp.fboundp(lisp['make-progress-reporter']):
            progress = _LispProgress(name)
        else:
            progress = _OldProgress(name)
        return progress

    def show_occurrences(self, locations):
        text = []
        for filename, offset, note in locations:
            line = '%s : %s %s' % (filename, offset, note)
            text.append(line)
        text = '\n'.join(text) + '\n'
        buffer = self.make_buffer('*rope-occurrences*', text, switch=True)
        lisp.set_buffer(buffer)
        lisp.local_set_key('\r', lisp.rope_occurrences_goto_occurrence)
        lisp.local_set_key('q', lisp.delete_window)

    def show_doc(self, docs):
        fit_lines = self.get('ropemacs-max-doc-buffer-height')
        buffer = self.make_buffer('*rope-pydoc*', docs,
                                  empty_goto=False, fit_lines=fit_lines)
        lisp.local_set_key('q', lisp.bury_buffer)


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


class RunTask(object):

    def __init__(self, task, name, interrupts=True):
        self.task = task
        self.name = name
        self.interrupts = interrupts

    def __call__(self):
        handle = taskhandle.TaskHandle(name=self.name)
        progress = LispUtils().create_progress(self.name)
        def update_progress():
            jobset = handle.current_jobset()
            if jobset:
                percent = jobset.get_percent_done()
                if percent is not None:
                    progress.update(percent)
        handle.add_observer(update_progress)
        result = self.task(handle)
        progress.done()
        return result


def occurrences_goto_occurrence():
    start = lisp.line_beginning_position()
    end = lisp.line_end_position()
    line = lisp.buffer_substring_no_properties(start, end)
    tokens = line.split()
    if tokens:
        filename = tokens[0]
        offset = int(tokens[2])
        resource = _interface._get_resource(filename)
        LispUtils().find_file(resource.real_path, other=True)
        lisp.goto_char(offset + 1)
        lisp.switch_to_buffer_other_window('*rope-occurrences*')
occurrences_goto_occurrence.interaction = ''


def _register_functions(interface):
    for attrname in dir(interface):
        attr = getattr(interface, attrname)
        if hasattr(attr, 'interaction') or hasattr(attr, 'lisp'):
            globals()[attrname] = attr


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

(defcustom ropemacs-separate-doc-buffer t
  "Should `rope-show-doc' use a separate buffer or the minibuffer.")
(defcustom ropemacs-max-doc-buffer-height 22
  "The maximum buffer height for `rope-show-doc'.")

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

(defcustom ropemacs-enable-shortcuts 't
  "Shows whether to bind ropemacs shortcuts keys.

If non-nil it binds:

================  ============================
Key               Command
================  ============================
M-/               rope-code-assist
C-c g             rope-goto-definition
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

(provide 'ropemacs)
"""

MINOR_MODE = """\
(define-minor-mode ropemacs-mode
 "ropemacs, rope in emacs!" nil " Rope" ropemacs-local-keymap
  :global nil)
)
"""

lisp(DEFVARS)
_interface = ropecommon.interface.Ropemacs(env=LispUtils())
_register_functions(_interface)
_interface.init()
lisp(MINOR_MODE)
