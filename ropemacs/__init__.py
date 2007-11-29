"""ropemacs, an emacs mode for using rope refactoring library"""

from Pymacs import lisp
from rope.base import project, libutils
from rope.contrib import codeassist

from ropemacs import refactor, lisputils
from ropemacs.lisputils import lispfunction, interactive


VERSION = '0.3'


class RopeInterface(object):

    def __init__(self):
        self.project = None
        self.old_content = None
        self.global_keys = [
            ('C-x p o', lisp.rope_open_project),
            ('C-x p k', lisp.rope_close_project),
            ('C-x p u', lisp.rope_undo_refactoring),
            ('C-x p r', lisp.rope_redo_refactoring),
            ('C-x p f', lisp.rope_find_file),
            ('C-x p c', lisp.rope_project_config)]

        self.local_keys = [
            ('M-/', lisp.rope_code_assist),
            ('C-c g', lisp.rope_goto_definition),
            ('C-c C-d', lisp.rope_show_doc),
            ('C-c f', lisp.rope_find_occurrences)]

        self._register_refactorings()

    @lispfunction
    def init(self):
        """Initialize rope mode"""
        lisp.add_hook(lisp.before_save_hook, lisp.rope_before_save_actions)
        lisp.add_hook(lisp.after_save_hook, lisp.rope_after_save_actions)
        lisp.add_hook(lisp.kill_emacs_hook, lisp.rope_exiting_actions)
        lisp.add_hook(lisp.python_mode_hook, lisp.rope_register_local_keys)

        lisp(DEFVARS)

        for key, callback in self.global_keys:
            lisp.global_set_key(self._key_sequence(key), callback)

    def _register_refactorings(self):
        for name in dir(refactor):
            if not name.startswith('_') and name != 'Refactoring':
                attr = getattr(refactor, name)
                if isinstance(attr, type) and issubclass(attr, refactor.Refactoring):
                    @interactive
                    def do_refactor(self=self, refactoring=attr):
                        refactoring(self).show()
                    setattr(self, attr.name, do_refactor)
                    name = 'rope-' + attr.name.replace('_', '-')
                    self.local_keys.append((attr.key, lisp[name]))

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

    @lispfunction
    def before_save_actions(self):
        if self.project is not None:
            resource = self._get_resource()
            if resource is not None and resource.exists():
                self.old_content = resource.read()
            else:
                self.old_content = ''

    @lispfunction
    def after_save_actions(self):
        if self.project is not None:
            libutils.report_change(self.project, lisp.buffer_file_name(),
                                   self.old_content)
            self.old_content = None

    @lispfunction
    def register_local_keys(self):
        for key, callback in self.local_keys:
            lisp.local_set_key(self._key_sequence(key), callback)

    @lispfunction
    def exiting_actions(self):
        if self.project is not None:
            self.close_project()

    @interactive
    def open_project(self):
        root = lisp.read_directory_name('Rope project root folder: ')
        if self.project is not None:
            self.close_project()
        self.project = project.Project(root)

    @interactive
    def close_project(self):
        if project is not None:
            self.project.close()
            self.project = None
            lisp.message('Project closed')

    @interactive
    def undo_refactoring(self):
        if lisp.y_or_n_p('Undo refactoring might change'
                         ' many files; proceed? '):
            self._check_project()
            for changes in self.project.history.undo():
                self._reload_buffers(changes.get_changed_resources())

    @interactive
    def redo_refactoring(self):
        if lisp.y_or_n_p('Redo refactoring might change'
                         ' many files; proceed? '):
            self._check_project()
            for changes in self.project.history.redo():
                self._reload_buffers(changes.get_changed_resources())

    def _get_region(self):
        offset1 = self._get_offset()
        lisp.exchange_point_and_mark()
        offset2 = self._get_offset()
        lisp.exchange_point_and_mark()
        return min(offset1, offset2), max(offset1, offset2)

    def _get_offset(self):
        return lisp.point() - 1

    @interactive
    def goto_definition(self):
        self._check_project()
        resource, offset = self._get_location()
        definition = codeassist.get_definition_location(
            self.project, lisp.buffer_string(), offset, resource)
        if tuple(definition) != (None, None):
            lisp.push_mark()
            self._goto_location(definition)

    @interactive
    def show_doc(self):
        self._check_project()
        resource, offset = self._get_location()
        docs = codeassist.get_doc(
            self.project, lisp.buffer_string(), offset, resource)
        lisputils.make_buffer('*rope-pydoc*', docs, empty_goto=False)

    @interactive
    def find_occurrences(self):
        self._check_project()
        self._save_buffers()
        resource, offset = self._get_location()
        def calculate(handle):
            return codeassist.find_occurrences(
                self.project, resource, offset,
                unsure=True, task_handle=handle)
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
            lisp.goto_char(offset)
            lisp.switch_to_buffer_other_window('*rope-occurrences*')

    @interactive
    def code_assist(self):
        self._check_project()
        resource, offset = self._get_location()
        source = lisp.buffer_string()
        proposals = codeassist.code_assist(self.project, source,
                                           offset, resource)
        proposals = codeassist.sorted_proposals(proposals)
        starting_offset = codeassist.starting_offset(source, offset)
        names = [proposal.name for proposal in proposals]
        starting = source[starting_offset:offset]
        prompt = 'Completion for %s: ' % starting
        result = lisputils.ask_values(prompt, names,
                                      starting=starting, exact=None)
        lisp.delete_region(starting_offset + 1, offset + 1)
        lisp.insert(result)

    @interactive
    def find_file(self):
        self._check_project()
        files = self.project.get_files()
        names = []
        for file in files:
            names.append('<'.join(reversed(file.path.split('/'))))
        source = lisp.buffer_string()
        result = lisputils.ask_values('Rope Find File: ', names, exact=True)
        path = '/'.join(reversed(result.split('<')))
        file = self.project.get_file(path)
        lisp.find_file(file.real_path)

    @interactive
    def project_config(self):
        self._check_project()
        if self.project.ropefolder is not None:
            config = self.project.ropefolder.get_child('config.py')
            lisp.find_file(config.real_path)
        else:
            lisputils.message('No rope project folder found')

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
            lisp.call_interactively(lisp.rope_open_project)
        else:
            self.project.validate(self.project.root)

    def _reload_buffers(self, changed_resources):
        for resource in changed_resources:
            buffer = lisp.find_buffer_visiting(str(resource.real_path))
            if buffer and resource.exists():
                lisp.set_buffer(buffer)
                lisp.revert_buffer(None, 1)

    def _save_buffers(self, only_current=False):
        ask = lisp['rope-confirm-saving'].value()
        initial = lisp.current_buffer()
        current_buffer = lisp.current_buffer()
        if only_current:
            buffers = [current_buffer]
        else:
            buffers = lisp.buffer_list()
        for buffer in buffers:
            filename = lisp.buffer_file_name(buffer)
            if filename:
                if self._is_a_project_python_file(filename) and \
                   lisp.buffer_modified_p(buffer):
                    if not ask or lisp.y_or_n_p('Save %s buffer?' % filename):
                        lisp.set_buffer(buffer)
                        lisp.save_buffer()
        lisp.set_buffer(initial)

    def _is_a_project_python_file(self, path):
        resource = self._get_resource(path)
        return (resource is not None and resource.exists() and
                resource.project == self.project and
                self.project.pycore.is_python_file(resource))


def _register_functions(interface):
    for attrname in dir(interface):
        attr = getattr(interface, attrname)
        if hasattr(attr, 'interaction') or hasattr(attr, 'lisp'):
            globals()[attrname] = attr


DEFVARS = """\
(defvar rope-confirm-saving t
  "If non-nil, you have to confirm saving all modified
python files before refactorings; otherwise they are
saved automatically.")
"""

interface = RopeInterface()
_register_functions(interface)
