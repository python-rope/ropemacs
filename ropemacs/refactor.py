import rope.base.taskhandle
import rope.contrib.generate
import rope.refactor.extract
import rope.refactor.inline
import rope.refactor.move
import rope.refactor.rename
import rope.refactor.restructure

from ropemacs import dialog, lisputils


class Refactoring(object):

    name = None
    key = None
    confs = {}
    optionals = {}
    saveall = True

    def __init__(self, interface):
        self.interface = interface

    def show(self):
        self.interface._check_project()
        self.interface._save_buffers(only_current=not self.saveall)
        self._create_refactoring()
        action, result = dialog.show_dialog(
            lisputils.askdata, ['perform', 'preview', 'cancel'],
            self._get_confs(), self._get_optionals())
        if action == 'cancel':
            lisputils.message('Cancelled!')
            return
        def calculate(handle):
            return self._calculate_changes(result, handle)
        name = 'Calculating %s changes' % self.name
        changes = lisputils.RunTask(calculate, name=name)()
        if action == 'perform':
            self._perform(changes)
        if action == 'preview':
            if changes is not None:
                diffs = str(changes.get_description())
                lisputils.make_buffer('*rope-preview*', diffs, modes=['diff'])
                if lisputils.yes_or_no('Do the changes? '):
                    self._perform(changes)
                else:
                    lisputils.message('Thrown away!')
                lisputils.hide_buffer('*rope-preview*')
            else:
                lisputils.message('No changes!')

    @property
    def project(self):
        return self.interface.project

    @property
    def resource(self):
        return self.interface._get_resource()

    @property
    def offset(self):
        return self.interface._get_offset()

    @property
    def region(self):
        return self.interface._get_region()

    def _calculate_changes(self, option_values, task_handle):
        pass

    def _create_refactoring(self):
        pass

    def _done(self):
        pass

    def _perform(self, changes):
        if changes is None:
            lisputils.message('No changes!')
            return
        def perform(handle, self=self, changes=changes):
            self.project.do(changes, task_handle=handle)
            self.interface._reload_buffers(changes.get_changed_resources())
            self._done()
        lisputils.RunTask(perform, 'Making %s changes' % self.name,
                           interrupts=False)()
        lisputils.message(str(changes.description) + ' finished')

    def _get_confs(self):
        return self.confs

    def _get_optionals(self):
        return self.optionals


class Rename(Refactoring):

    name = 'rename'
    key = 'C-c r r'
    optionals = {
        'docs': dialog.Data('Rename occurrences in comments and docs: ',
                            values=['yes', 'no'], default='yes'),
        'in_hierarchy': dialog.Data('Method in class hierarchy: ',
                                    values=['yes', 'no'], default='no'),
        'in_file': dialog.Data('Only rename occurrences in the same file: ',
                               values=['yes', 'no'], default='no'),
        'unsure': dialog.Data('Unsure occurrences: ',
                              values=['ignore', 'match'], default='ignore')}
    saveall = True

    def __init__(self, interface):
        self.interface = interface

    def _create_refactoring(self):
        self.renamer = rope.refactor.rename.Rename(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        newname = values['newname']
        unsure = values.get('unsure', 'ignore') == 'match'
        kwds = {
            'docs': values.get('docs', 'yes') == 'yes',
            'in_file': values.get('in_file', 'no') == 'yes',
            'unsure': (lambda occurrence: unsure)}
        if self.renamer.is_method():
            kwds['in_hierarchy'] = values.get('in_hierarchy', 'no') == 'yes'
        return self.renamer.get_changes(newname,
                                        task_handle=task_handle, **kwds)

    def _get_confs(self):
        oldname = str(self.renamer.get_old_name())
        return {'newname': dialog.Data('New name: ', starting=oldname)}


class RenameCurrentModule(Rename):

    name = 'rename_current_module'
    key = 'C-c r 1 r'
    offset = None


class Restructure(Refactoring):

    name = 'restructure'
    key = 'C-c r x'
    confs = {'pattern': dialog.Data('Restructuring pattern: '),
             'goal': dialog.Data('Restructuring goal: ')}
    optionals = {'checks': dialog.Data('Checks: '),
                 'imports': dialog.Data('Imports: ')}

    def _calculate_changes(self, values, task_handle):
        restructuring = rope.refactor.restructure.Restructure(
            self.project, values['pattern'], values['goal'])
        check_dict = {}
        for raw_check in values.get('checks', '').split('\n'):
            if raw_check:
                key, value = raw_check.split('==')
                check_dict[key.strip()] = value.strip()
        checks = restructuring.make_checks(check_dict)
        imports = [line.strip()
                   for line in values.get('imports', '').split('\n')]
        return restructuring.get_changes(checks=checks, imports=imports,
                                         task_handle=task_handle)


class Move(Refactoring):

    name = 'move'
    key = 'C-c r v'

    def _create_refactoring(self):
        self.mover = rope.refactor.move.create_move(self.project,
                                                    self.resource,
                                                    self.offset)

    def _calculate_changes(self, values, task_handle):
        destination = values['destination']
        if isinstance(self.mover, rope.refactor.move.MoveGlobal):
            return self._move_global(destination, task_handle)
        if isinstance(self.mover, rope.refactor.move.MoveModule):
            return self._move_module(destination, task_handle)
        if isinstance(self.mover, rope.refactor.move.MoveMethod):
            return self._move_method(destination, task_handle)

    def _move_global(self, dest, handle):
        destination = self.project.pycore.find_module(dest)
        return self.mover.get_changes(destination, task_handle=handle)

    def _move_method(self, dest, handle):
        return self.mover.get_changes(
            dest, self.mover.get_method_name(), task_handle=handle)

    def _move_module(self, dest, handle):
        destination = self.project.pycore.find_module(dest)
        return self.mover.get_changes(destination, task_handle=handle)

    def _get_confs(self):
        if isinstance(self.mover, rope.refactor.move.MoveGlobal):
            prompt = 'Destination module: '
        if isinstance(self.mover, rope.refactor.move.MoveModule):
            prompt = 'Destination package: '
        if isinstance(self.mover, rope.refactor.move.MoveMethod):
            prompt = 'Destination attribute: '
        return {'destination': dialog.Data(prompt)}


class MoveCurrentModule(Move):

    name = 'move_current_module'
    key = 'C-c r 1 v'

    offset = None


class ModuleToPackage(Refactoring):

    name = 'module_to_package'
    key = 'C-c r 1 p'
    saveall = False

    def _create_refactoring(self):
        self.packager = rope.refactor.ModuleToPackage(
            self.project, self.resource)

    def _calculate_changes(self, values, task_handle):
        return self.packager.get_changes()


class Inline(Refactoring):

    name = 'inline'
    key = 'C-c r i'
    optionals = {'remove': dialog.Data('Remove the definition: ',
                                       values=['yes', 'no'])}

    def _create_refactoring(self):
        self.inliner = rope.refactor.inline.create_inline(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        remove = values.get('remove', 'yes') == 'yes'
        return self.inliner.get_changes(remove=remove,
                                        task_handle=task_handle)


class ExtractVariable(Refactoring):

    name = 'extract_variable'
    key = 'C-c r l'
    saveall = False
    confs = {'name': dialog.Data('Extracted variable name: ')}

    def _create_refactoring(self):
        start, end = self.region
        self.extractor = rope.refactor.extract.ExtractVariable(
            self.project, self.resource, start, end)

    def _calculate_changes(self, values, task_handle):
        return self.extractor.get_changes(values['name'])


class ExtractMethod(Refactoring):

    name = 'extract_method'
    key = 'C-c r m'
    saveall = False
    confs = {'name': dialog.Data('Extracted method name: ')}

    def _create_refactoring(self):
        start, end = self.region
        self.extractor = rope.refactor.extract.ExtractMethod(
            self.project, self.resource, start, end)

    def _calculate_changes(self, values, task_handle):
        return self.extractor.get_changes(values['name'])


class OrganizeImports(Refactoring):

    name = 'organize_imports'
    key = 'C-c i o'
    saveall = False

    def _create_refactoring(self):
        self.organizer = rope.refactor.ImportOrganizer(self.project)

    def _calculate_changes(self, values, task_handle):
        return self.organizer.organize_imports(self.resource)


class _GenerateElement(Refactoring):

    def _create_refactoring(self):
        kind = self.name.split('_')[-1]
        self.generator = rope.contrib.generate.create_generate(
            kind, self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        return self.generator.get_changes()

    def _done(self):
        self.interface._goto_location(self.generator.get_location())


class GenerateVariable(_GenerateElement):

    name = 'generate_variable'
    key = 'C-c n v'


class GenerateFunction(_GenerateElement):

    name = 'generate_function'
    key = 'C-c n f'


class GenerateClass(_GenerateElement):

    name = 'generate_class'
    key = 'C-c n c'


class GenerateModule(_GenerateElement):

    name = 'generate_module'
    key = 'C-c n m'


class GeneratePackage(_GenerateElement):

    name = 'generate_package'
    key = 'C-c n p'
