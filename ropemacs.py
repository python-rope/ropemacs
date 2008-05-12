"""ropemacs, an emacs mode for using rope refactoring library"""

import ropecommon.dialog
import ropecommon.interface
import ropecommon.lisputils
import traceback

from Pymacs import lisp
from rope.base import taskhandle, exceptions


def _register_functions(interface):
    for attrname in dir(interface):
        attr = getattr(interface, attrname)
        if hasattr(attr, 'interaction') or hasattr(attr, 'lisp'):
            globals()[attrname] = attr


_interface = ropecommon.interface.Ropemacs()
_register_functions(_interface)
_interface.init()
