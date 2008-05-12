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

    def get_region(self):
        offset1 = self._get_offset()
        lisp.exchange_point_and_mark()
        offset2 = self._get_offset()
        lisp.exchange_point_and_mark()
        return min(offset1, offset2), max(offset1, offset2)

    def get_offset(self):
        return lisp.point() - 1

    def get_text(self):
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


def _register_functions(interface):
    for attrname in dir(interface):
        attr = getattr(interface, attrname)
        if hasattr(attr, 'interaction') or hasattr(attr, 'lisp'):
            globals()[attrname] = attr


_interface = ropecommon.interface.Ropemacs(env=LispUtils())
_register_functions(_interface)
_interface.init()
