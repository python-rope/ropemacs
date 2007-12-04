=========================
 ropemacs, rope in emacs
=========================

Ropemacs is an emacs mode that uses rope_ library to provide features
like refactorings and code-assists.  You should install rope_ library
and Pymacs before using ropemacs.

.. _`rope`: http://rope.sf.net/


New Features
============

* Find occurrences; ``C-c f``
* Lucky-assist; ``M-?``
* Setting many configs using batchset in dialogs
* Showing the old value of a field in dialogs
* New file/directory/module/package; ``C-x p n [fdmp]``
* Edit project config; ``C-x p c``
* Updating buffers with moved files after refactorings


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


Code-Assist
-----------

``rope-code-assist`` command (``M-/`` by default) will let you select
from a list of completions.  If prefixed (``C-u M-/``), ropemacs
inserts the common prefix, automatically.  If a numeric argument is
given, rope will insert the common prefix for that many of the first
proposals.

``rope-lucky-assist`` command (``M-?``) does not ask, anything;
instead, it inserts the first proposal.  By prefixing it, you can
choose which proposal to insert.  ``C-u 1 M-?`` uses the second
propsal, for instance.

Here::

  xxaa = None
  xxab = None
  xxba = None
  xxbb = None

  x^

consider cursor is at ``^`` position.  This table shows what happens
when code-assist commands are used:

============  ==========  =======================
Key           Inserts     Minibuffer Completions
============  ==========  =======================
M-/                       xxaa, xxab, xxba, xxbb
C-u M-/       x           xxaa, xxab, xxba, xxbb
C-u 2 M-/     xa          xxaa, xxab
M-?           xxaa
C-u 1 M-/     xxab
C-u 3 M-/     xxbb
============  ==========  =======================


Dialog ``batchset`` Command
---------------------------

When you use rope dialogs there is a command called ``batchset``.  It
can be used to set many configs at the same time.  After selecting
this command from dialog base prompt, you are asked to enter a string.

``batchset`` strings can give value to configs in two ways.  The
single line form is like this::

  name1 value1
  name2 value2

That is the name of config is followed its value.  For multi-line
values you can use::

  name1
   line1
   line2

  name2
   line3

Each line of the definition should start with a space or a tab.  Note
that blank lines before the name of config definitions are ignored.

``batchset`` command is useful when performing refactorings with long
configs, like restructurings::

  pattern ${?pycore}.create_module(${?project}.root, ${?name})

  goal generate.create_module(${?project}, ${?name})

  imports
   from rope.contrib import generate

  checks
   ?pycore.type == rope.base.pycore.PyCore
   ?project.type == rope.base.project.Project

.. ignore the two-space indents

This is a valid ``batchset`` string for restructurings.  When using
batchset, you usually want to skip initial questions.  That can be
done by prefixing refactorings.

Just for the sake of completeness, the reverse of the above
restructuring can be::

  pattern ${?create_module}(${?project}, ${?name})

  goal ${?project}.pycore.create_module(${?project}.root, ${?name})

  checks
   ?create_module == rope.contrib.generate.create_module
   ?project.type == rope.base.project.Project


Key-binding
-----------

Uses almost the same keybinding as ropeide.

==============  ============================
Key             Command
==============  ============================
C-x p o         rope-open-project
C-x p k         rope-close-project
C-x p f         rope-find-file
C-x p u         rope-undo-refactoring
C-x p r         rope-redo-refactoring
C-x p c         rope-project-config
C-x p n [mpfd]  rope-create-(module|package|file|directory)

C-c r r         rope-rename
C-c r l         rope-extract-variable
C-c r m         rope-extract-method
C-c r i         rope-inline
C-c r v         rope-move
C-c r x         rope-restructure
C-c r 1 r       rope-rename-current-module
C-c r 1 v       rope-move-current-module
C-c r 1 p       rope-module-to-package

M-/             rope-code-assist
C-c g           rope-goto-definition
C-c C-d         rope-show-doc
C-c i o         rope-organize-imports
C-c f           rope-find-occurrences
M-?             rope-lucky-assist
C-c n [vfcmp]   rope-generate-(variable|function|class|module|package)
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
