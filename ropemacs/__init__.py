"""ropemacs, an emacs mode for using rope refactoring library"""

import ropemacs.dialog
import ropemacs.lisputils
import ropemacs.interface


def _register_functions(interface):
    for attrname in dir(interface):
        attr = getattr(interface, attrname)
        if hasattr(attr, 'interaction') or hasattr(attr, 'lisp'):
            globals()[attrname] = attr


@ropemacs.lisputils.lispfunction
def init():
    ropemacs.lisputils.lisp.warn(
        'Calling (rope-init) is no longer needed.')

interface = ropemacs.interface.Ropemacs()
_register_functions(interface)
interface.init()
