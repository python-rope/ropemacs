import threading

from Pymacs import lisp
from rope.base import taskhandle, exceptions


def yes_or_no(prompt):
    return lisp.yes_or_no_p(prompt)


def make_buffer(name, contents, empty_goto=True, mode=None):
    new_buffer = lisp.get_buffer_create(name)
    lisp.set_buffer(new_buffer)
    lisp.erase_buffer()
    if contents or empty_goto:
        lisp.insert(contents)
        if mode is not None:
            lisp[mode + '-mode']()
        lisp.display_buffer(new_buffer)
        lisp.goto_line(1)


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
            message('%s interrupted!' % self.name)
            raise
        return calculate.result


def message(message):
    lisp.message(message)


def askdata(data):
    """`data` is a `ropemacs.dialog.Data` object"""
    if data.values:
        return ask_values(data.prompt, data.values, default=data.default,
                          starting=data.starting)
    else:
        return ask(data.prompt, default=data.default, starting=data.starting)


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
    result =  lisp.read_from_minibuffer(prompt, starting, None, None,
                                        None, default, None)
    if result == '' and default is not None:
        return default
    return result


def lispfunction(func):
    func.lisp = None
    return func


def interactive(func):
    func.interaction = ''
    return func
