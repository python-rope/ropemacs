import rope.base.change
from Pymacs import lisp
from rope.base import libutils
from rope.contrib import codeassist, generate

import ropemacs
from ropemacs import refactor, lisputils
from ropemacs.lisputils import (lispfunction, interactive,
                                prefixed, rawprefixed, lisphook)


class Ropemacs(object):

    def __init__(self):
        self.project = None
        self.old_content = None
        lisp(DEFVARS)

        self.global_keys = [
            ('o', lisp.rope_open_project),
            ('k', lisp.rope_close_project),
            ('u', lisp.rope_undo),
            ('r', lisp.rope_redo),
            ('f', lisp.rope_find_file),
            ('4 f', lisp.rope_find_file_other_window),
            ('c', lisp.rope_project_config),
            ('n m', lisp.rope_create_module),
            ('n p', lisp.rope_create_package),
            ('n f', lisp.rope_create_file),
            ('n d', lisp.rope_create_directory)]

        self.local_keys = [
            ('/', lisp.rope_code_assist),
            ('?', lisp.rope_lucky_assist),
            ('g', lisp.rope_goto_definition),
            ('d', lisp.rope_show_doc),
            ('f', lisp.rope_find_occurrences)]
        self.shortcuts = [
            ('M-/', lisp.rope_code_assist),
            ('M-?', lisp.rope_lucky_assist),
            ('C-c g', lisp.rope_goto_definition),
            ('C-c d', lisp.rope_show_doc),
            ('C-c f', lisp.rope_find_occurrences)]
        self.hooks = (
            (lisp.before_save_hook, lisp.rope_before_save_actions),
            (lisp.after_save_hook, lisp.rope_after_save_actions),
            (lisp.kill_emacs_hook, lisp.rope_exiting_actions),
            (lisp.python_mode_hook, lisp.rope_register_local_keys))
        self._prepare_refactorings()

    def init(self):
        """Initialize rope mode"""
        for hook, function in self.hooks:
            lisp.add_hook(hook, function)

        prefix = lisp.ropemacs_global_prefix.value()
        if prefix is not None:
            for key, callback in self.global_keys:
                lisp.global_set_key(self._key_sequence(prefix + ' ' + key),
                                    callback)

    def _prepare_refactorings(self):
        for name in dir(refactor):
            if not name.startswith('_') and name != 'Refactoring':
                attr = getattr(refactor, name)
                if isinstance(attr, type) and \
                   issubclass(attr, refactor.Refactoring):
                    @rawprefixed
                    def do_refactor(prefix, self=self, refactoring=attr):
                        initial_asking = prefix is None
                        refactoring(self).show(initial_asking=initial_asking)
                    name = self._refactoring_name(attr)
                    setattr(self, name, do_refactor)
                    name = 'rope-' + name.replace('_', '-')
                    if attr.key is not None:
                        self.local_keys.append((attr.key, lisp[name]))

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

    @lisphook
    def before_save_actions(self):
        if self.project is not None:
            if not self._is_python_file(lisp.buffer_file_name()):
                return
            resource = self._get_resource()
            if resource.exists():
                self.old_content = resource.read()
            else:
                self.old_content = ''

    @lisphook
    def after_save_actions(self):
        if self.project is not None and self.old_content is not None:
            libutils.report_change(self.project, lisp.buffer_file_name(),
                                   self.old_content)
            self.old_content = None

    @lisphook
    def register_local_keys(self):
        prefix = lisp.ropemacs_local_prefix.value()
        for key, callback in self.local_keys:
            if prefix is not None:
                key = prefix + ' ' + key
                lisp.local_set_key(self._key_sequence(key), callback)
        for key, callback in self.shortcuts:
            if lisp['ropemacs-enable-shortcuts'].value():
                lisp.local_set_key(self._key_sequence(key), callback)

    @lisphook
    def exiting_actions(self):
        if self.project is not None:
            self.close_project()

    @lispfunction
    def unload_hook(self):
        """Unload registered hooks"""
        for hook, function in self.hooks:
            lisp.remove_hook(hook, function)

    @interactive
    def open_project(self):
        root = lisputils.ask_directory('Rope project root folder: ')
        if self.project is not None:
            self.close_project()
        progress = lisputils.create_progress('Opening "%s" project' % root)
        self.project = rope.base.project.Project(root)
        progress.done()

    @interactive
    def close_project(self):
        if self.project is not None:
            progress = lisputils.create_progress('Closing "%s" project' %
                                                 self.project.address)
            self.project.close()
            self.project = None
            progress.done()

    @interactive
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
            lisputils.RunTask(undo, 'Undo refactoring', interrupts=False)()

    @interactive
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
            lisputils.RunTask(redo, 'Redo refactoring', interrupts=False)()

    def _get_region(self):
        offset1 = self._get_offset()
        lisp.exchange_point_and_mark()
        offset2 = self._get_offset()
        lisp.exchange_point_and_mark()
        return min(offset1, offset2), max(offset1, offset2)

    def _get_offset(self):
        return lisp.point() - 1

    def _get_text(self):
        end = lisp.buffer_size() + 1
        old_min = lisp.point_min()
        old_max = lisp.point_max()
        narrowed = (old_min != 1 or old_max != end)
        if narrowed:
            lisp.narrow_to_region(1, lisp.buffer_size() + 1)
        try:
            #result = lisp.buffer_string()
	    coding_name = self._find_file_coding()
            result = lisp('(encode-coding-string'
                          ' (buffer-string) buffer-file-coding-system)')
            if coding_name:
                if coding_name.endswith('dos'):
                    result = result.replace('\r', '')
                if coding_name.split('-')[-1] in ('dos', 'unix', 'mac'):
                    coding_name = coding_name[:coding_name.rindex('-')]
                if coding_name.split('-')[0] in ('mule', 'iso'):
                    coding_name = coding_name[coding_name.index('-') + 1:]
                try:
                    result = unicode(result, coding_name)
                except (LookupError, UnicodeDecodeError):
                    result = unicode(result, 'utf-8')
            return result
        finally:
            if narrowed:
                lisp.narrow_to_region(old_min, old_max)

    def _find_file_coding(self):
        if lisp.fboundp(lisp['coding-system-name']):
            coding = lisp('(coding-system-name'
                          ' buffer-file-coding-system)')
        else:
            coding = lisp['buffer-file-coding-system'].value()
        if isinstance(coding, str):
            return coding
        if coding is not None and hasattr(coding, 'text'):
            return coding.text

    @interactive
    def goto_definition(self):
        self._check_project()
        resource, offset = self._get_location()
        definition = codeassist.get_definition_location(
            self.project, self._get_text(), offset, resource)
        if tuple(definition) != (None, None):
            lisp.push_mark()
            self._goto_location(definition)

    @interactive
    def show_doc(self):
        self._check_project()
        resource, offset = self._get_location()
        docs = codeassist.get_doc(
            self.project, self._get_text(), offset, resource)
        buffer = lisputils.make_buffer('*rope-pydoc*', docs, empty_goto=False)
        lisp.local_set_key('q', lisp.bury_buffer)

    @interactive
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
            result = lisputils.RunTask(calculate, 'Find Occurrences')()
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


    @interactive
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

    @interactive
    def occurrences_quit(self):
        lisputils.hide_buffer('*rope-occurrences*')

    @rawprefixed
    def code_assist(self, prefix):
        starting_offset, names = self._calculate_proposals()
        if prefix is not None:
            arg = lisp.prefix_numeric_value(prefix)
            if arg == 0:
                arg = len(names)
            common_start = self._calculate_prefix(names[:arg])
            lisp.insert(common_start[self._get_offset() - starting_offset:])
        source = self._get_text()
        offset = self._get_offset()
        starting = source[starting_offset:offset]
        prompt = 'Completion for %s: ' % starting
        result = lisputils.ask_values(prompt, names,
                                      starting=starting, exact=None)
        lisp.delete_region(starting_offset + 1, offset + 1)
        lisp.insert(result)

    @rawprefixed
    def lucky_assist(self, prefix):
        starting_offset, names = self._calculate_proposals()
        source = self._get_text()
        offset = self._get_offset()
        starting = source[starting_offset:offset]
        selected = 0
        if prefix is not None:
            selected = lisp.prefix_numeric_value(prefix)
        if 0 <= selected < len(names):
            result = names[selected]
        else:
            lisputils.message('Not enough proposals!')
            return
        lisp.delete_region(starting_offset + 1, offset + 1)
        lisp.insert(result)

    def _calculate_proposals(self):
        self._check_project()
        resource, offset = self._get_location()
        source = self._get_text()
        maxfixes = lisp['ropemacs-codeassist-maxfixes'].value()
        proposals = codeassist.code_assist(self.project, source, offset,
                                           resource, maxfixes=maxfixes)
        proposals = codeassist.sorted_proposals(proposals)
        starting_offset = codeassist.starting_offset(source, offset)
        names = [proposal.name for proposal in proposals]
        return starting_offset, names

    def _calculate_prefix(self, names):
        if not names:
            return ''
        prefix = names[0]
        for name in names:
            common = 0
            for c1, c2 in zip(prefix, name):
                if c1 == c2:
                    common += 1
                else:
                    break
            prefix = prefix[:common]
        return prefix

    @interactive
    def find_file(self):
        file = self._base_find_file()
        lisp.find_file(file.real_path)

    @interactive
    def find_file_other_window(self):
        file = self._base_find_file()
        lisp.find_file_other_window(file.real_path)

    def _base_find_file(self):
        self._check_project()
        files = self.project.get_files()
        names = []
        for file in files:
            names.append('<'.join(reversed(file.path.split('/'))))
        result = lisputils.ask_values('Rope Find File: ', names, exact=True)
        path = '/'.join(reversed(result.split('<')))
        file = self.project.get_file(path)
        return file

    @interactive
    def project_config(self):
        self._check_project()
        if self.project.ropefolder is not None:
            config = self.project.ropefolder.get_child('config.py')
            lisp.find_file(config.real_path)
        else:
            lisputils.message('No rope project folder found')


    @interactive
    def create_module(self):
        def callback(sourcefolder, name):
            return generate.create_module(self.project, name, sourcefolder)
        self._create('module', callback)

    @interactive
    def create_package(self):
        def callback(sourcefolder, name):
            folder = generate.create_package(self.project, name, sourcefolder)
            return folder.get_child('__init__.py')
        self._create('package', callback)

    @interactive
    def create_file(self):
        def callback(parent, name):
            return parent.create_file(name)
        self._create('file', callback, 'parent')

    @interactive
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
        resource = libutils.path_to_resource(self.project, filename, 'file')
        return resource

    def _check_project(self):
        if self.project is None:
            self.open_project()
        else:
            self.project.validate(self.project.root)

    def _reload_buffers(self, changes, undo=False):
        self._reload_buffers_for_changes(changes.get_changed_resources(),
                             self._get_moved_resources(changes, undo))

    def _reload_buffers_for_changes(self, changed_resources,
                                    moved_resources={}):
        for resource in changed_resources:
            buffer = lisp.find_buffer_visiting(str(resource.real_path))
            if buffer:
                if resource.exists():
                    lisp.set_buffer(buffer)
                    lisp.revert_buffer(None, 1)
                elif resource in moved_resources:
                    new_resource = moved_resources[resource]
                    lisp.kill_buffer(buffer)
                    lisp.find_file(new_resource.real_path)

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

(provide 'ropemacs)
"""
