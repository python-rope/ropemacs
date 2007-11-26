=========================
 ropemacs, rope in emacs
=========================

Ropemacs is an emacs mode that uses rope_ library to provide features
like refactorings and code-assists.  You should install rope_ library
and Pymacs before using ropemacs.

.. _`rope`: http://rope.sf.net/


New Features
============

* Auto-completing python names (code-assist); ``M-/``
* Rope find file; ``C-c p f``
* Generate python element; ``C-c n [vfcmp]``


Setting Up
==========

You can get Pymacs from http://www.iro.umontreal.ca/~pinard/pymacs/.
But version 0.22 does not work with Python 2.5 because of the lack of
file encoding declarations.  A simple patch is included:
``docs/pymacs_python25.patch``.

After installing pymacs, add these lines to your ``~/.emacs`` file::

  (require 'pymacs)
  (pymacs-load "ropemacs" "rope-")
  (rope-init)


Keybinding
==========

Uses almost the same keybinding as rope.

=============   ============================
Key             Action
=============   ============================
C-x p o         rope-open-project
C-x p k         rope-close-project
C-x p u         rope-undo-refactoring
C-x p r         rope-redo-refactoring
C-x p f         rope-find-file

C-c r r         rope-rename
C-c r l         rope-extract-variable
C-c r m         rope-extract-method
C-c r i         rope-inline
C-c r v         rope-move
C-c r 1 r       rope-rename-current-module
C-c r 1 v       rope-move-current-module
C-c r 1 p       rope-module-to-package

C-/             rope-code-assist
C-c g           rope-goto-definition
C-c C-d         rope-show-doc
C-c i o         rope-organize-imports

C-c n v         rope-generate-variable
C-c n f         rope-generate-function
C-c n c         rope-generate-class
C-c n m         rope-generate-module
C-c n p         rope-generate-package
=============   ============================


Contributing
============

Send your bug reports, feature requests and patches to `rope-dev (at)
googlegroups.com`_.

.. _`rope-dev (at) googlegroups.com`: http://groups.google.com/group/rope-dev



License
=======

This program is under the terms of GPL (GNU General Public License).
Have a look at ``COPYING`` file for more information.
