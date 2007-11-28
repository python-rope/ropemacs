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

Rope registers its local keys using ``python-mode`` hook.  If you
don't want to use rope with ``python-mode`` you can add
``rope-register-local-keys`` lisp function to some other hook.

If you want to load ropemacs only when you really need it, you can use
a function like this instead of that::

  (defun load-ropemacs ()
    "Load pymacs and ropemacs"
    (interactive)
    (require 'pymacs)
    (pymacs-load "ropemacs" "rope-")
    (rope-init)
    (setq rope-confirm-saving 'nil)
  )

And execute ``load-ropemacs`` whenever you want to use ropemacs.  Also
if you don't want to install rope library and ropemacs you can put
them somewhere and add them to the ``PYTHONPATH`` before loading
ropemacs in your ``.emacs``::

  (setenv "PYTHONPATH" (concat (getenv "PYTHONPATH")
                               ":/path/to/extracted/rope/package"
                               ":/path/to/extracted/ropemacs/package"))


Getting Started
===============

Rope refactorings use a special kind of dialog.  When you start a
refactoring, you'll be asked to confirm saving modified python
buffers; you can change it by using ``rope-confirm-saving`` variable.
Adding ``(setq rope-confirm-saving 'nil)`` to your ``.emacs`` file,
will make emacs save them without asking.

After that depending on the refactoring, you'll be asked about the
essential information a refactoring needs to know (like the new name
in rename refactoring).

Next you'll see the base prompt of a refactoring dialog that shows
something like "Choose what to do".  You can choose to set other
optional refactoring options; after setting each option you'll be
returned back to the base prompt.  Finally, you can ask rope to
perform, preview or cancel the refactoring.

See keybinding_ section and try the refactorings yourself.


Finding Files
-------------

By using ``rope-find-file`` (``C-x p f`` by default), you can search
for files in your project.  When you complete the minibuffer you'll
see all files in the project; files are shown as their reversed paths.
For instance ``projectroot/docs/todo.txt`` is shown like
``todo.txt<docs``.  This way you can find files faster in your
project.


Keybinding
----------

Uses almost the same keybinding as ropeide.

==============  ============================
Key             Action
==============  ============================
C-x p o         rope-open-project
C-x p k         rope-close-project
C-x p f         rope-find-file
C-x p u         rope-undo-refactoring
C-x p r         rope-redo-refactoring

C-c r r         rope-rename
C-c r l         rope-extract-variable
C-c r m         rope-extract-method
C-c r i         rope-inline
C-c r v         rope-move
C-c r 1 r       rope-rename-current-module
C-c r 1 v       rope-move-current-module
C-c r 1 p       rope-module-to-package

M-/             rope-code-assist
C-c g           rope-goto-definition
C-c C-d         rope-show-doc
C-c i o         rope-organize-imports

C-c n v         rope-generate-variable
C-c n f         rope-generate-function
C-c n c         rope-generate-class
C-c n m         rope-generate-module
C-c n p         rope-generate-package
==============  ============================


Variables
---------

* ``rope-confirm-saving``: If non-nil, you have to confirm saving all
  modified python files before refactorings; otherwise they are saved
  automatically. Defaults to ``t``.


Contributing
============

Send your bug reports, feature requests and patches to `rope-dev (at)
googlegroups.com`_.

.. _`rope-dev (at) googlegroups.com`: http://groups.google.com/group/rope-dev


License
=======

This program is under the terms of GPL (GNU General Public License).
Have a look at ``COPYING`` file for more information.
