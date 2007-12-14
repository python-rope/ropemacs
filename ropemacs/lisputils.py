import sys
import traceback
import threading

from Pymacs import lisp
from rope.base import taskhandle, exceptions


def yes_or_no(prompt):
    return lisp.yes_or_no_p(prompt)


def make_buffer(name, contents, empty_goto=True, switch=False, modes=[]):
    new_buffer = lisp.get_buffer_create(name)
    lisp.set_buffer(new_buffer)
    lisp.toggle_read_only(-1)
    lisp.erase_buffer()
    if contents or empty_goto:
        lisp.insert(contents)
        for mode in modes:
            lisp[mode + '-mode']()
        lisp.display_buffer(new_buffer)
        lisp.buffer_disable_undo(new_buffer)
        lisp.toggle_read_only(1)
        if switch:
            lisp.switch_to_buffer_other_window(new_buffer)
        lisp.goto_line(1)
    return new_buffer


def hide_buffer(name):
    buffer = lisp.get_buffer(name)
    if buffer is not None:
        window = lisp.get_buffer_window(buffer)
        if window is not None:
            lisp.delete_window(window)
            lisp.bury_buffer(buffer)


class RunTask(object):

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
                self.traceback = None

            def __call__(self):
                try:
                    self.result = self.task(handle)
                except Exception, e:
                    self.exception = e
                    self.traceback = str(traceback.format_exc())

        calculate = Calculate(self.task)
        thread = threading.Thread(target=calculate)
        try:
            thread.start()
            thread.join()
            lisp.progress_reporter_done(progress)
            raised = calculate.exception
            if raised is not None:
                description = type(raised).__name__ + ': ' + str(raised)
                raise exceptions.InterruptedTaskError(
                    'Task <%s> was interrupted.\nReason: <%s>\nTraceback: %s' %
                    (self.name, description, calculate.traceback))
        except:
            handle.stop()
            message('%s interrupted!' % self.name)
            raise
        return calculate.result


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
    result = lisp.read_directory_name(prompt, starting, default)
    if result == '' and default is not None:
        return default
    return result


def lispfunction(func):
    func.lisp = None
    return func


def interactive(func):
    func.interaction = ''
    return func

def prefixed(func):
    func.interaction = 'p'
    return func

def rawprefixed(func):
    func.interaction = 'P'
    return func

def lisphook(func):
    def newfunc(*args, **kwds):
        try:
            func(*args, **kwds)
        except Exception, e:
            message('Exception in ropemacs hook: %s' %
                    (type(e).__name__ + str(e)))
    newfunc.interaction = ''
    return newfunc
