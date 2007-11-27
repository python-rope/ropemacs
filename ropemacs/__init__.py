import threading

from Pymacs import lisp
from rope.base import project, libutils, taskhandle, exceptions
from rope.contrib import codeassist

from ropemacs import refactor


def interactive(func):
    func.interaction = ''
    return func

def lispfunction(func):
    func.lisp = None
    return func


class RopeInterface(object):

    def __init__(self):
        self.project = None
        self.old_content = None
        self.global_keys = [
            ('C-x p o', lisp.rope_open_project),
            ('C-x p k', lisp.rope_close_project),
            ('C-x p u', lisp.rope_undo_refactoring),
            ('C-x p r', lisp.rope_redo_refactoring),
            ('C-x p f', lisp.rope_find_file)]

        self.local_keys = [
            ('M-/', lisp.rope_code_assist),
            ('C-c g', lisp.rope_goto_definition),
            ('C-c C-d', lisp.rope_show_doc)]

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
        lisp.push_mark()
        self._goto_location(definition)

    @interactive
    def show_doc(self):
        self._check_project()
        resource, offset = self._get_location()
        docs = codeassist.get_doc(
            self.project, lisp.buffer_string(), offset, resource)
        _make_buffer('*rope-pydoc*', docs, empty_goto=False)

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
        result = _ask_values(prompt, names, starting=starting, exact=None)
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
        result = _ask_values('Rope Find File: ', names, exact=True)
        path = '/'.join(reversed(result.split('<')))
        file = self.project.get_file(path)
        lisp.find_file(file.real_path)

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


def _ask(prompt, default=None, starting=None):
    if default is not None:
        prompt = prompt + ('[%s] ' % default)
    result =  lisp.read_from_minibuffer(prompt, starting, None, None,
                                        None, default, None)
    if result == '' and default is not None:
        return default
    return result

def _ask_values(prompt, values, default=None, starting=None, exact=True):
    if exact and default is not None:
        prompt = prompt + ('[%s] ' % default)
    result = lisp.completing_read(prompt, values, None, exact, starting)
    if result == '' and exact:
        return default
    return result

def _lisp_askdata(data):
    if data.values:
        return _ask_values(data.prompt, data.values, default=data.default,
                           starting=data.starting)
    else:
        return _ask(data.prompt, default=data.default, starting=data.starting)

def _message(message):
    lisp.message(message)


class _RunTask(object):

    def __init__(self, task, name, interrupts=True):
        self.task = task
        self.name = name
        self.interrupts = interrupts

    def __call__(self):
        handle = taskhandle.TaskHandle(name=self.name)
        progress = lisp.make_progress_reporter(
            '%s ... ' % self.name, 0, 100)
        def update_progress():
            jobset = handle.current_jobset()
            if jobset:
                percent = jobset.get_percent_done()
                if percent is not None:
                    lisp.progress_reporter_update(progress, percent)
        handle.add_observer(update_progress)
        class Calculate(object):

            def __init__(self, task):
                self.task = task
                self.result = None
                self.exception = None

            def __call__(self):
                try:
                    self.result = self.task(handle)
                except Exception, e:
                    self.exception = e

        calculate = Calculate(self.task)
        thread = threading.Thread(target=calculate)
        try:
            thread.start()
            thread.join()
            lisp.progress_reporter_done(progress)
            if calculate.exception is not None:
                description = type(calculate.exception).__name__ + ': ' + \
                                   str(calculate.exception)
                raise exceptions.InterruptedTaskError(
                    'Task <%s> was interrupted.\nReason: <%s>' %
                    (self.name, description))
        except:
            handle.stop()
            _message('%s interrupted!' % self.name)
            raise
        return calculate.result


def _make_buffer(name, contents, empty_goto=True, mode=None):
    new_buffer = lisp.get_buffer_create(name)
    lisp.set_buffer(new_buffer)
    lisp.erase_buffer()
    if contents or empty_goto:
        lisp.insert(contents)
        if mode is not None:
            lisp[mode + '-mode']()
        lisp.display_buffer(new_buffer)
        lisp.goto_line(1)

def _yes_or_no(prompt):
    return lisp.yes_or_no_p(prompt)


DEFVARS = """\
(defvar rope-confirm-saving t
  "If non-nil, you have to confirm saving all modified
python files before refactorings; otherwise they are
saved automatically.")
"""

interface = RopeInterface()
_register_functions(interface)
