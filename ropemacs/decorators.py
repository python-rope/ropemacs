import traceback

from rope.base import exceptions

from ropemacs import lisputils


def lisphook(func):
    def newfunc(*args, **kwds):
        try:
            func(*args, **kwds)
        except Exception, e:
            trace = str(traceback.format_exc())
            lisputils.message(
                '%s\nIgnored an exception in ropemacs hook: %s: %s' %
                (trace, type(e).__name__, str(e)))
    newfunc.lisp = None
    newfunc.__name__ = func.__name__
    newfunc.__doc__ = func.__doc__
    return newfunc


def interactive(func):
    func.interaction = ''
    return func


def lispfunction(func):
    func.lisp = None
    return func


input_exceptions = (exceptions.RefactoringError,)

def _lisp_name(func):
    return 'rope-' + func.__name__.replace('_', '-')

def _exception_handler(func):
    def newfunc(*args, **kwds):
        try:
            func(*args, **kwds)
        except exceptions.RopeError, e:
            if isinstance(e, input_exceptions):
                lisputils.message('%s: %s' % (e.__class__.__name__, str(e)))
            else:
                raise e
    newfunc.__name__ = func.__name__
    newfunc.__doc__ = func.__doc__
    return newfunc

def rope_hook(hook):
    def decorator(func):
        func = lisphook(func)
        func.lisp_name = _lisp_name(func)
        func.kind = 'hook'
        func.hook = hook
        return func
    return decorator


def local_command(key=None, interaction='', shortcut=None, name=None):
    def decorator(func, name=name):
        func = _exception_handler(func)
        func.kind = 'local'
        if interaction is not None:
            func.interaction = interaction
        func.local_key = key
        func.shortcut_key = shortcut
        if name is None:
            name = _lisp_name(func)
        func.lisp_name = name
        return func
    return decorator


def global_command(key=None, interaction=''):
    def decorator(func):
        func = _exception_handler(func)
        func.kind = 'global'
        if interaction is not None:
            func.interaction = interaction
        func.global_key = key
        func.lisp_name = _lisp_name(func)
        return func
    return decorator
