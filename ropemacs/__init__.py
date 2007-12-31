"""ropemacs, an emacs mode for using rope refactoring library"""

import ropemacs.dialog
import ropemacs.interface
import ropemacs.lisputils


COPYRIGHT = """\
Copyright (C) 2007-2008 Ali Gholami Rudi

This program is free software; you can redistribute it and/or modify it
under the terms of GNU General Public License as published by the
Free Software Foundation; either version 2 of the license, or (at your
opinion) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details."""


def _register_functions(interface):
    for attrname in dir(interface):
        attr = getattr(interface, attrname)
        if hasattr(attr, 'interaction') or hasattr(attr, 'lisp'):
            globals()[attrname] = attr


def init():
    ropemacs.lisputils.lisp.warn(
        'Calling (rope-init) is no longer needed.')

interface = ropemacs.interface.Ropemacs()
_register_functions(interface)
interface.init()
