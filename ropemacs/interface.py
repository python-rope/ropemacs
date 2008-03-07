import rope.base.change
from Pymacs import lisp
from rope.base import libutils
from rope.contrib import codeassist, generate, autoimport

import ropemacs
from ropemacs import refactor, lisputils


def _lisp_name(func):
    return 'rope-' + func.__name__.replace('_', '-')

def global_command(key=None, interaction=''):
    def decorator(func):
        if interaction is not None:
            func.interaction = interaction
        if key:
            global_keys.append((key, _lisp_name(func)))
        return func
    return decorator

def local_command(key=None, interaction='', shortcut=None, name=None):
    def decorator(func, name=name):
        if name is None:
            name = _lisp_name(func)
        if interaction is not None:
            func.interaction = interaction
        if key:
            local_keys.append((key, name))
        if shortcut:
            shortcuts.append((shortcut, name))
        return func
    return decorator

def rope_hook(hook):
    def decorator(func):
        name = _lisp_name(func)
        func = lisputils.lisphook(func)
        hooks.append((hook, name))
        return func
    return decorator

global_keys = []
local_keys = []
shortcuts = []
hooks = [('python-mode-hook', 'ropemacs-mode')]

class Ropemacs(object):

    def __init__(self):
        self.project = None
        self.old_content = None
        lisp(DEFVARS)

        self._prepare_refactorings()
        self.autoimport = None
        self._init_ropemacs_keymap()
        lisp(MINOR_MODE)

    def init(self):
        """Initialize rope mode"""
        for hook, function in hooks:
            lisp.add_hook(lisp[hook], lisp[function])

        prefix = lisp.ropemacs_global_prefix.value()
        if prefix is not None:
            for key, callback in global_keys:
                lisp.global_set_key(self._key_sequence(prefix + ' ' + key),
                                    lisp[callback])

    def _prepare_refactorings(self):
        for name in dir(refactor):
            if not name.startswith('_') and name != 'Refactoring':
                attr = getattr(refactor, name)
                if isinstance(attr, type) and \
                   issubclass(attr, refactor.Refactoring):
                    ref_name = self._refactoring_name(attr)
                    lisp_name = 'rope-' + ref_name.replace('_', '-')
                    @local_command(attr.key, 'P', None, lisp_name)
                    def do_refactor(prefix, self=self, refactoring=attr):
                        initial_asking = prefix is None
                        refactoring(self).show(initial_asking=initial_asking)
                    setattr(self, ref_name, do_refactor)

    def _refactoring_name(self, refactoring):
        return refactor.refactoring_name(refactoring)

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

    @rope_hook('before-save-hook')
    def before_save_actions(self):
        if self.project is not None:
            if not self._is_python_file(lisp.buffer_file_name()):
                return
            resource = self._get_resource()
            if resource.exists():
                self.old_content = resource.read()
            else:
                self.old_content = ''

    @rope_hook('after-save-hook')
    def after_save_actions(self):
        if self.project is not None and self.old_content is not None:
            libutils.report_change(self.project, lisp.buffer_file_name(),
                                   self.old_content)
            self.old_content = None

    def _init_ropemacs_keymap(self):
        prefix = lisp.ropemacs_local_prefix.value()
        for key, callback in local_keys:
            if prefix is not None:
                key = prefix + ' ' + key
                lisp('(define-key ropemacs-local-keymap "%s" \'%s)' %
                     (self._key_sequence(key), callback))
        for key, callback in shortcuts:
            if lisp['ropemacs-enable-shortcuts'].value():
                lisp('(define-key ropemacs-local-keymap "%s" \'%s)' %
                     (self._key_sequence(key), callback))

    @rope_hook('kill-emacs-hook')
    def exiting_actions(self):
        if self.project is not None:
            self.close_project()

    @lisputils.lispfunction
    def unload_hook(self):
        """Unload registered hooks"""
        for hook, function in hooks:
            lisp.remove_hook(lisp[hook], lisp[function])

    @global_command('o')
    def open_project(self):
        root = lisputils.ask_directory('Rope project root folder: ')
        if self.project is not None:
            self.close_project()
        progress = lisputils.create_progress('Opening "%s" project' % root)
        self.project = rope.base.project.Project(root)
        if lisp['ropemacs-enable-autoimport'].value():
            self.autoimport = autoimport.AutoImport(self.project)
        progress.done()

    @global_command('k')
    def close_project(self):
        if self.project is not None:
            progress = lisputils.create_progress('Closing "%s" project' %
                                                 self.project.address)
            self.project.close()
            self.project = None
            progress.done()

    @global_command()
    def write_project(self):
        if self.project is not None:
            progress = lisputils.create_progress(
                'Writing "%s" project data to disk' % self.project.address)
            self.project.sync()
            progress.done()

    @global_command('u')
    def undo(self):
        self._check_project()
        change = self.project.history.tobe_undone
        if change is None:
            lisputils.message('Nothing to undo!')
            return
        if lisp.y_or_n_p('Undo <%s>? ' % str(change)):
            def undo(handle):
                for changes in self.project.history.undo(task_handle=handle):
                    self._reload_buffers(changes, undo=True)
            lisputils.runtask(undo, 'Undo refactoring', interrupts=False)

    @global_command('r')
    def redo(self):
        self._check_project()
        change = self.project.history.tobe_redone
        if change is None:
            lisputils.message('Nothing to redo!')
            return
        if lisp.y_or_n_p('Redo <%s>? ' % str(change)):
            def redo(handle):
                for changes in self.project.history.redo(task_handle=handle):
                    self._reload_buffers(changes)
            lisputils.runtask(redo, 'Redo refactoring', interrupts=False)

    def _get_region(self):
        offset1 = self._get_offset()
        lisp.exchange_point_and_mark()
        offset2 = self._get_offset()
        lisp.exchange_point_and_mark()
        return min(offset1, offset2), max(offset1, offset2)

    def _get_offset(self):
        return lisp.point() - 1

    def _get_text(self):
        if not lisp.buffer_modified_p():
            return self._get_resource().read()
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

    @local_command('a g', shortcut='C-c g')
    def goto_definition(self):
        self._check_project()
        resource, offset = self._get_location()
        maxfixes = lisp['ropemacs-codeassist-maxfixes'].value()
        definition = codeassist.get_definition_location(
            self.project, self._get_text(), offset, resource, maxfixes)
        if tuple(definition) != (None, None):
            lisp.push_mark()
            self._goto_location(definition)

    @local_command('a d', 'P', 'C-c d')
    def show_doc(self, prefix):
        self._check_project()
        self._base_show_doc(prefix)

    @local_command(interaction='P')
    def show_call_doc(self, prefix):
        self._check_project()
        offset = self._get_offset()
        text = self._get_text()
        try:
            offset = text.rindex('(', 0, offset) - 1
            self._base_show_doc(prefix, text, offset)
        except ValueError:
            lisputils.message('Not inside a function')

    def _base_show_doc(self, prefix, text=None, offset=None):
        maxfixes = lisp['ropemacs-codeassist-maxfixes'].value()
        if text is None:
            text = self._get_text()
        if offset is None:
            offset = self._get_offset()
        docs = codeassist.get_doc(self.project, text, offset,
                                  self._get_resource(), maxfixes)

        use_minibuffer = not prefix
        if lisp['ropemacs-separate-doc-buffer'].value():
            use_minibuffer = not use_minibuffer
        if use_minibuffer and docs:
            docs = '\n'.join(docs.split('\n')[:7])
            lisputils.message(docs)
        else:
            buffer = lisputils.make_buffer('*rope-pydoc*', docs,
                                           empty_goto=False)
            lisp.local_set_key('q', lisp.bury_buffer)

    @local_command('a f', shortcut='C-c f')
    def find_occurrences(self):
        self._check_project()
        self._save_buffers()
        resource, offset = self._get_location()

        optionals = {
            'unsure': ropemacs.dialog.Data('Find uncertain occurrences: ',
                                           default='no', values=['yes', 'no']),
            'resources': ropemacs.dialog.Data('Files to search: ')}
        action, values = ropemacs.dialog.show_dialog(
            lisputils.askdata, ['search', 'cancel'], optionals=optionals)
        if action == 'search':
            unsure = values.get('unsure') == 'yes'
            resources = ropemacs.refactor._resources(self.project,
                                                     values.get('resources'))
            def calculate(handle):
                return codeassist.find_occurrences(
                    self.project, resource, offset,
                    unsure=unsure, resources=resources, task_handle=handle)
            result = lisputils.runtask(calculate, 'Find Occurrences')
            text = []
            for occurrence in result:
                line = '%s : %s' % (occurrence.resource.path, occurrence.offset)
                if occurrence.unsure:
                    line += ' ?'
                text.append(line)
            text = '\n'.join(text) + '\n'
            buffer = lisputils.make_buffer('*rope-occurrences*',
                                           text, switch=True)
            lisp.set_buffer(buffer)
            lisp.local_set_key('\r', lisp.rope_occurrences_goto_occurrence)
            lisp.local_set_key('q', lisp.rope_occurrences_quit)


    @lisputils.interactive
    def occurrences_goto_occurrence(self):
        self._check_project()
        start = lisp.line_beginning_position()
        end = lisp.line_end_position()
        line = lisp.buffer_substring_no_properties(start, end)
        tokens = line.split()
        if tokens:
            resource = self.project.get_resource(tokens[0])
            offset = int(tokens[2])
            lisp.find_file_other_window(resource.real_path)
            lisp.goto_char(offset + 1)
            lisp.switch_to_buffer_other_window('*rope-occurrences*')

    @lisputils.interactive
    def occurrences_quit(self):
        lisputils.hide_buffer('*rope-occurrences*')

    @local_command('a /', 'P', 'M-/')
    def code_assist(self, prefix):
        _CodeAssist(self).code_assist(prefix)

    @local_command('a ?', 'P', 'M-?')
    def lucky_assist(self, prefix):
        _CodeAssist(self).lucky_assist(prefix)

    @local_command()
    def auto_import(self):
        _CodeAssist(self).auto_import()

    def _check_autoimport(self):
        self._check_project()
        if self.autoimport is None:
            lisputils.message('autoimport is disabled; '
                              'see `ropemacs-enable-autoimport\' variable')
            return False
        return True

    @global_command()
    def generate_autoimport_cache(self):
        if not self._check_autoimport():
            return
        modules = lisp['ropemacs-autoimport-modules'].value()
        modnames = []
        if modules:
            for i in range(len(modules)):
                modname = modules[i]
                if not isinstance(modname, basestring):
                    modname = modname.value()
                modnames.append(modname)
        def generate(handle):
            self.autoimport.generate_cache(task_handle=handle)
            self.autoimport.generate_modules_cache(modules, task_handle=handle)
        lisputils.runtask(generate, 'Generate autoimport cache')

    @global_command('f', 'P')
    def find_file(self, prefix):
        file = self._base_find_file(prefix)
        if file is not None:
            lisp.find_file(file.real_path)

    @global_command('4 f', 'P')
    def find_file_other_window(self, prefix):
        file = self._base_find_file(prefix)
        if file is not None:
            lisp.find_file_other_window(file.real_path)

    def _base_find_file(self, prefix):
        self._check_project()
        if prefix:
            files = self.project.pycore.get_python_files()
        else:
            files = self.project.get_files()
        names = []
        for file in files:
            names.append('<'.join(reversed(file.path.split('/'))))
        result = lisputils.ask_values('Rope Find File: ', names, exact=True)
        if result is not None:
            path = '/'.join(reversed(result.split('<')))
            file = self.project.get_file(path)
            return file
        lisputils.message('No file selected')

    @global_command('c')
    def project_config(self):
        self._check_project()
        if self.project.ropefolder is not None:
            config = self.project.ropefolder.get_child('config.py')
            lisp.find_file(config.real_path)
        else:
            lisputils.message('No rope project folder found')

    @global_command('n m')
    def create_module(self):
        def callback(sourcefolder, name):
            return generate.create_module(self.project, name, sourcefolder)
        self._create('module', callback)

    @global_command('n p')
    def create_package(self):
        def callback(sourcefolder, name):
            folder = generate.create_package(self.project, name, sourcefolder)
            return folder.get_child('__init__.py')
        self._create('package', callback)

    @global_command('n f')
    def create_file(self):
        def callback(parent, name):
            return parent.create_file(name)
        self._create('file', callback, 'parent')

    @global_command('n d')
    def create_directory(self):
        def callback(parent, name):
            parent.create_folder(name)
        self._create('directory', callback, 'parent')

    def _create(self, name, callback, parentname='source'):
        self._check_project()
        confs = {'name': ropemacs.dialog.Data(name.title() + ' name: ')}
        parentname = parentname + 'folder'
        optionals = {parentname: ropemacs.dialog.Data(
                parentname.title() + ' Folder: ',
                default=self.project.address, kind='directory')}
        action, values = ropemacs.dialog.show_dialog(
            lisputils.askdata, ['perform', 'cancel'], confs, optionals)
        if action == 'perform':
            parent = libutils.path_to_resource(
                self.project, values.get(parentname, self.project.address))
            resource = callback(parent, values['name'])
            if resource:
                lisp.find_file(resource.real_path)

    def _goto_location(self, location, readonly=False):
        if location[0]:
            resource = location[0]
            if resource.project == self.project:
                lisp.find_file(str(location[0].real_path))
            else:
                lisp.find_file_read_only(str(location[0].real_path))
        if location[1]:
            lisp.goto_line(location[1])

    def _get_location(self):
        resource = self._get_resource()
        offset = self._get_offset()
        return resource, offset

    def _get_resource(self, filename=None):
        if filename is None:
            filename = lisp.buffer_file_name()
        if filename is None:
            return
        resource = libutils.path_to_resource(self.project, filename, 'file')
        return resource

    def _check_project(self):
        if self.project is None:
            self.open_project()
        else:
            self.project.validate(self.project.root)

    def _reload_buffers(self, changes, undo=False):
        self._reload_buffers_for_changes(
            changes.get_changed_resources(),
            self._get_moved_resources(changes, undo))

    def _reload_buffers_for_changes(self, changed_resources,
                                    moved_resources={}):
        if self._get_resource() in moved_resources:
            initial = None
        else:
            initial = lisp.current_buffer()
        for resource in changed_resources:
            buffer = lisp.find_buffer_visiting(str(resource.real_path))
            if buffer:
                if resource.exists():
                    lisp.set_buffer(buffer)
                    lisp.revert_buffer(False, True)
                elif resource in moved_resources:
                    new_resource = moved_resources[resource]
                    lisp.kill_buffer(buffer)
                    lisp.find_file(new_resource.real_path)
        if initial is not None:
            lisp.set_buffer(initial)

    def _get_moved_resources(self, changes, undo=False):
        result = {}
        if isinstance(changes, rope.base.change.ChangeSet):
            for change in changes.changes:
                result.update(self._get_moved_resources(change))
        if isinstance(changes, rope.base.change.MoveResource):
            result[changes.resource] = changes.new_resource
        if undo:
            return dict([(value, key) for key, value in result.items()])
        return result

    def _save_buffers(self, only_current=False):
        ask = lisp['ropemacs-confirm-saving'].value()
        initial = lisp.current_buffer()
        current_buffer = lisp.current_buffer()
        if only_current:
            buffers = [current_buffer]
        else:
            buffers = lisp.buffer_list()
        for buffer in buffers:
            filename = lisp.buffer_file_name(buffer)
            if filename:
                if self._is_python_file(filename) and \
                   lisp.buffer_modified_p(buffer):
                    if not ask or lisp.y_or_n_p('Save %s buffer?' % filename):
                        lisp.set_buffer(buffer)
                        lisp.save_buffer()
        lisp.set_buffer(initial)

    def _is_python_file(self, path):
        resource = self._get_resource(path)
        return (resource is not None and
                resource.project == self.project and
                self.project.pycore.is_python_file(resource))


class _CodeAssist(object):

    def __init__(self, interface):
        self.interface = interface
        self.autoimport = interface.autoimport
        self._source = None
        self._offset = None
        self._starting_offset = None
        self._starting = None
        self._expression = None

    def code_assist(self, prefix):
        names = self._calculate_proposals()
        if prefix is not None:
            arg = lisp.prefix_numeric_value(prefix)
            if arg == 0:
                arg = len(names)
            common_start = self._calculate_prefix(names[:arg])
            lisp.insert(common_start[self.offset - self.starting_offset:])
            self._starting = common_start
            self._offset = self.starting_offset + len(common_start)
        prompt = 'Completion for %s: ' % self.expression
        result = lisputils.ask_values(prompt, names,
                                      starting=self.starting, exact=None)
        self._apply_assist(result)

    def lucky_assist(self, prefix):
        names = self._calculate_proposals()
        selected = 0
        if prefix is not None:
            selected = lisp.prefix_numeric_value(prefix)
        if 0 <= selected < len(names):
            result = names[selected]
        else:
            lisputils.message('Not enough proposals!')
            return
        self._apply_assist(result)

    def auto_import(self):
        if not self.interface._check_autoimport():
            return
        name = lisp.current_word()
        modules = self.autoimport.get_modules(name)
        if modules:
            if len(modules) == 1:
                module = modules[0]
            else:
                module = lisputils.ask_values(
                    'Which module to import: ', modules)
            self._insert_import(name, module)
        else:
            lisputils.message('Global name %s not found!' % name)

    def _apply_assist(self, assist):
        if ' : ' in assist:
            name, module = assist.rsplit(' : ', 1)
            lisp.delete_region(self.starting_offset + 1, self.offset + 1)
            lisp.insert(name)
            self._insert_import(name, module)
        else:
            lisp.delete_region(self.starting_offset + 1, self.offset + 1)
            lisp.insert(assist)

    def _calculate_proposals(self):
        self.interface._check_project()
        resource = self.interface._get_resource()
        maxfixes = lisp['ropemacs-codeassist-maxfixes'].value()
        proposals = codeassist.code_assist(
            self.interface.project, self.source, self.offset,
            resource, maxfixes=maxfixes)
        proposals = codeassist.sorted_proposals(proposals)
        names = [proposal.name for proposal in proposals]
        if self.autoimport is not None:
            if self.starting.strip() and '.' not in self.expression:
                import_assists = self.autoimport.import_assist(self.starting)
                names.extend(x[0] + ' : ' + x[1] for x in import_assists)
        return names

    def _insert_import(self, name, module):
        lineno = self.autoimport.find_insertion_line(self.source)
        current = lisp.point()
        lisp.goto_line(lineno)
        newimport = 'from %s import %s\n' % (module, name)
        lisp.insert(newimport)
        lisp.goto_char(current + len(newimport))

    def _calculate_prefix(self, names):
        if not names:
            return ''
        prefix = names[0]
        for name in names:
            common = 0
            for c1, c2 in zip(prefix, name):
                if c1 != c2 or ' ' in (c1, c2):
                    break
                common += 1
            prefix = prefix[:common]
        return prefix

    @property
    def offset(self):
        if self._offset is None:
            self._offset = self.interface._get_offset()
        return self._offset

    @property
    def source(self):
        if self._source is None:
            self._source = self.interface._get_text()
        return self._source

    @property
    def starting_offset(self):
        if self._starting_offset is None:
            self._starting_offset = codeassist.starting_offset(self.source,
                                                               self.offset)
        return self._starting_offset

    @property
    def starting(self):
        if self._starting is None:
            self._starting = self.source[self.starting_offset:self.offset]
        return self._starting

    @property
    def expression(self):
        if self._expression is None:
            self._expression = codeassist.starting_expression(self.source,
                                                              self.offset)
        return self._expression


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

(defcustom ropemacs-enable-autoimport 'nil
  "Specifies whether autoimport should be enabled.")
(defcustom ropemacs-autoimport-modules nil
  "The name of modules whose global names should be cached.

The `rope-generate-autoimport-cache' reads this list and fills its
cache.")

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

(provide 'ropemacs)
"""

MINOR_MODE = """\
(define-minor-mode ropemacs-mode
 "ropemacs, rope in emacs!" nil " Rope" ropemacs-local-keymap
  :global nil)
)
"""
