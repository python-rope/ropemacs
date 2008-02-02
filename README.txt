=========================
 ropemacs, rope in emacs
=========================

Ropemacs is an emacs mode that uses rope_ library to provide features
like refactorings and code-assists.  You should install rope_ library
and pymacs_ before using ropemacs.

.. _`rope`: http://rope.sf.net/
.. _pymacs: http://www.iro.umontreal.ca/~pinard/pymacs/


New Features
============


Setting Up
==========

Pymacs_ has not been maintained for a few years.  I've started a new
Mercurial repo and applied a few fixes which is available at
http://rope.sf.net/hg/rpymacs.  Also you can download `rpymacs
snapshot`_.

After installing pymacs, add these lines to your ``~/.emacs`` file::

  (require 'pymacs)
  (pymacs-load "ropemacs" "rope-")

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
    ;; Automatically save project python buffers before refactorings
    (setq ropemacs-confirm-saving 'nil)
  )

And execute ``load-ropemacs`` whenever you want to use ropemacs.  Also
if you don't want to install rope library and ropemacs you can extract
them somewhere and add these lines to your ``.emacs``::

  ;; Add this before loading pymacs if you haven't installed rope and ropemacs
  (setq pymacs-load-path '("/home/ali/projects/rope"
                           "/home/ali/projects/ropemacs"))

.. _`rpymacs snapshot`: http://rope.sf.net/hg/rpymacs/archive/tip.tar.gz


Getting Started
===============

Rope refactorings use a special kind of dialog.  When you start a
refactoring, you'll be asked to confirm saving modified python
buffers; you can change it by using ``ropemacs-confirm-saving``
variable.  Adding ``(setq ropemacs-confirm-saving 'nil)`` to your
``.emacs`` file, will make emacs save them without asking.

After that depending on the refactoring, you'll be asked about the
essential information a refactoring needs to know (like the new name
in rename refactoring).  You can skip it by prefixing the refactoring;
this can be useful when using batchset command (described later).

Next you'll see the base prompt of a refactoring dialog that shows
something like "Choose what to do".  By entering the name of a
refactoring option you can set its value.  After setting each option
you'll be returned back to the base prompt.  Finally, you can ask rope
to perform, preview or cancel the refactoring.

See keybinding_ section and try the refactorings yourself.


Finding Files
-------------

By using ``rope-find-file`` (``C-x p f`` by default), you can search
for files in your project.  When you complete the minibuffer you'll
see all files in the project; files are shown as their reversed paths.
For instance ``projectroot/docs/todo.txt`` is shown like
``todo.txt<docs``.  This way you can find files faster in your
project.  ``rope-find-file-other-window`` (``C-x p 4 f``) opens the
file in the other window.  With prefix, these commands show python
files only.


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


Finding Occurrences
-------------------

The find occurrences command (``C-c f`` by default) can be used to
find the occurrences of a python name.  If ``unsure`` option is
``yes``, it will also show unsure occurrences; unsure occurrences are
indicated with a ``?`` mark in the end.


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

  pattern ${pycore}.create_module(${project}.root, ${name})

  goal generate.create_module(${project}, ${name})

  imports
   from rope.contrib import generate

  args
   pycore: type=rope.base.pycore.PyCore
   project: type=rope.base.project.Project

.. ignore the two-space indents

This is a valid ``batchset`` string for restructurings.  When using
batchset, you usually want to skip initial questions.  That can be
done by prefixing refactorings.

Just for the sake of completeness, the reverse of the above
restructuring can be::

  pattern ${create_module}(${project}, ${name})

  goal ${project}.pycore.create_module(${project}.root, ${name})

  args
   create_module: name=rope.contrib.generate.create_module
   project: type=rope.base.project.Project


Key-binding
-----------

Uses almost the same keybinding as ropeide.  Note that global commands
have a ``C-x p`` prefix and commands have a ``C-c r`` prefix.  You can
change that (see variables_ section).

================  ============================
Key               Command
================  ============================
C-x p o           rope-open-project
C-x p k           rope-close-project
C-x p f           rope-find-file
C-x p 4 f         rope-find-file-other_window
C-x p u           rope-undo
C-x p r           rope-redo
C-x p c           rope-project-config
C-x p n [mpfd]    rope-create-(module|package|file|directory)
                  rope-write-project

C-c r r           rope-rename
C-c r l           rope-extract-variable
C-c r m           rope-extract-method
C-c r i           rope-inline
C-c r v           rope-move
C-c r x           rope-restructure
C-c r u           rope-use-function
C-c r 1 r         rope-rename-current-module
C-c r 1 v         rope-move-current-module
C-c r 1 p         rope-module-to-package

C-c r o           rope-organize-imports
C-c r n [vfcmp]   rope-generate-(variable|function|class|module|package)

C-c r /           rope-code-assist
C-c r g           rope-goto-definition
C-c r d           rope-show-doc
C-c r f           rope-find-occurrences
C-c r ?           rope-lucky-assist

                  rope-auto-import
                  rope-generate-autoimport-cache
===============   ============================

These shortcut keys are enabled only when
``ropemacs-enable-shortcuts`` variable is non-nil:

================  ============================
Key               Command
================  ============================
M-/               rope-code-assist
C-c g             rope-goto-definition
C-c d             rope-show-doc
C-c f             rope-find-occurrences
M-?               rope-lucky-assist
================  ============================


Enabling Autoimport
-------------------

Rope can propose and automatically import global names in other
modules.  But this feature disabled by default.  Before using them you
should add::

  (setq ropemacs-enable-autoimport 't)

to your ``~/.emacs`` file.  After enabling, rope maintains a cache of
global names for each project.  It updates the cache only when modules
are changed; if you want to cache all your modules at once, use
``rope-generate-autoimport-cache``.  It will cache all of the modules
inside a project plus those whose names are listed in
``ropemacs-autoimport-modules`` list::

  # add the name of modules you want to autoimport
  (setq ropemacs-autoimport-modules '("os" "shutil"))

Now if you are in a buffer that contains::

  rmtree

and you execute ``ropemacs-auto-import`` you'll end up with::

  from shutil import rmtree
  rmtree

Also ``rope-code-assist`` and ``rope-lucky-assist`` propose
auto-imported names by using ``name : module`` style.  Selecting them
will import the module automatically.


Variables
---------

* ``ropemacs-confirm-saving``: If non-nil, you have to confirm saving all
  modified python files before refactorings; otherwise they are saved
  automatically. Defaults to ``t``.
* ``ropemacs-codeassist-maxfixes``: The maximum number of syntax errors
  to fix for code assists.  The default value is ``1``.

* ``ropemacs-local-prefix``: The prefix for ropemacs refactorings.
  Defaults to ``C-c r``.
* ``ropemacs-global-prefix``: The prefix for ropemacs project commands
  Defaults to ``C-x p``.
* ``ropemacs-enable-shortcuts``: Shows whether to bind ropemacs
  shortcuts keys.  Defaults to ``t``.

* ``ropemacs-enable-autoimport``: Shows whether to enable autoimport.
* ``ropemacs-autoimport-modules``: The name of modules whose global
  names should be cached.  The `rope-generate-autoimport-cache' reads
  this list and fills its cache.


Contributing
============

Send your bug reports, feature requests and patches to `rope-dev (at)
googlegroups.com`_.

.. _`rope-dev (at) googlegroups.com`: http://groups.google.com/group/rope-dev


License
=======

This program is under the terms of GPL (GNU General Public License).
Have a look at ``COPYING`` file for more information.
