import traceback

from Pymacs import lisp
from rope.base import taskhandle, exceptions


def yes_or_no(prompt):
    return lisp.yes_or_no_p(prompt)


def make_buffer(name, contents, empty_goto=True,
                switch=False, window='other', modes=[],
                fit_lines=None):
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
        elif window == 'other':
            new_window = lisp.display_buffer(new_buffer)
            lisp.set_window_point(new_window, lisp.point_min())
            if fit_lines != None:
                max_height = min(fit_lines,
                                 lisp.count_lines(lisp.point_min(),
                                                  lisp.point_max())) + 1
                lisp.fit_window_to_buffer(new_window, max_height, max_height)

        lisp.goto_char(lisp.point_min())
    return new_buffer


def hide_buffer(name, delete=True):
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


class RunTask(object):

    def __init__(self, task, name, interrupts=True):
        self.task = task
        self.name = name
        self.interrupts = interrupts

    def __call__(self):
        handle = taskhandle.TaskHandle(name=self.name)
        progress = create_progress(self.name)
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


def runtask(command, name, interrupts=True):
    return RunTask(command, name, interrupts)()

def create_progress(name):
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


def message(message):
    lisp.message(message)


def askdata(data, starting=None):
    """`data` is a `ropemacs.dialog.Data` object"""
    ask_func = ask
    ask_args = {'prompt': data.prompt, 'starting': starting,
                'default': data.default}
    if data.values:
        ask_func = ask_values
        ask_args['values'] = data.values
    elif data.kind == 'directory':
        ask_func = ask_directory
    return ask_func(**ask_args)


def ask_values(prompt, values, default=None, starting=None, exact=True):
    if _emacs_version() < 22:
        values = [[value, value] for value in values]
    if exact and default is not None:
        prompt = prompt + ('[%s] ' % default)
    result = lisp.completing_read(prompt, values, None, exact, starting)
    if result == '' and exact:
        return default
    return result


def ask(prompt, default=None, starting=None):
    if default is not None:
        prompt = prompt + ('[%s] ' % default)
    result = lisp.read_from_minibuffer(prompt, starting, None, None,
                                        None, default, None)
    if result == '' and default is not None:
        return default
    return result

def ask_directory(prompt, default=None, starting=None):
    if default is not None:
        prompt = prompt + ('[%s] ' % default)
    if _emacs_version() < 22:
        result = lisp.read_file_name(prompt, starting, default)
    else:
        result = lisp.read_directory_name(prompt, starting, default)
    if result == '' and default is not None:
        return default
    return result

def _emacs_version():
    return int(lisp['emacs-version'].value().split('.')[0])


def lispfunction(func):
    func.lisp = None
    return func

def interactive(func):
    func.interaction = ''
    return func

def lisphook(func):
    def newfunc(*args, **kwds):
        try:
            func(*args, **kwds)
        except Exception, e:
            trace = str(traceback.format_exc())
            message('%s\nIgnored an exception in ropemacs hook: %s: %s' %
                    (trace, type(e).__name__, str(e)))
    newfunc.lisp = None
    return newfunc
