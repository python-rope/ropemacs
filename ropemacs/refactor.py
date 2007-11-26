import rope.contrib.generate
import rope.refactor.extract
import rope.refactor.inline
import rope.refactor.move
import rope.refactor.rename

import ropemacs
from ropemacs import config


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
        action, result = config.show_dialog(
            ropemacs._lisp_askdata, ['perform', 'cancel'],
            self._get_confs(), self._get_optionals())
        if action != 'perform':
            ropemacs._message('Cancelled!')
            return
        changes = self._calculate_changes(result)
        self._perform(changes)
        self._done()

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

    def _calculate_changes(self, option_values):
        pass

    def _create_refactoring(self):
        pass

    def _done(self):
        pass

    def _perform(self, changes):
        if changes is None:
            return
        self.project.do(changes)
        self.interface._reload_buffers(changes.get_changed_resources())
        ropemacs._message(str(changes.description) + ' finished')

    def _get_confs(self):
        return self.confs

    def _get_optionals(self):
        return self.optionals


class Rename(Refactoring):

    name = 'rename'
    key = 'C-c r r'
    optionals = {
        'docs': config.Data('Rename occurrences in comments and docs: ', values=['yes', 'no']),
        'in_hierarchy': config.Data('Method in class hierarchy: ', values=['yes', 'no']),
        'unsure': config.Data('Unsure occurrences: ', values=['ignore', 'match'])}
    saveall = True

    def __init__(self, interface):
        self.interface = interface

    def _create_refactoring(self):
        self.renamer = rope.refactor.rename.Rename(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values):
        newname = values['newname']
        unsure = values.get('unsure', 'no') == 'yes'
        kwds = {
            'docs': values.get('docs', 'yes') == 'yes',
            'unsure': (lambda occurrence: unsure)}
        if self.renamer.is_method():
            kwds['in_hierarchy'] = values.get('in_hierarchy', 'no') == 'yes'
        return self.renamer.get_changes(newname, **kwds)

    def _get_confs(self):
        oldname = str(self.renamer.get_old_name())
        return {'newname': config.Data('New name: ', starting=oldname)}


class RenameCurrentModule(Rename):

    name = 'rename_current_module'
    key = 'C-c r 1 r'
    offset = None


class Restructure(Refactoring):

    name = 'restructure'
    key = 'C-c r x'
    confs = {'pattern': config.Data('Restructuring pattern: '),
             'goal': config.Data('Restructuring goal: ')}
    optionals = {'checks': config.Data('Checks: '),
                     'imports': config.Data('Imports: ')}

    def _calculate_changes(self, values):
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
        return restructuring.get_changes(checks=checks, imports=imports)


class Move(Refactoring):

    name = 'move'
    key = 'C-c r v'

    def _create_refactoring(self):
        self.mover = rope.refactor.move.create_move(self.project,
                                                    self.resource,
                                                    self.offset)

    def _calculate_changes(self, values):
        destination = values['destination']
        if isinstance(self.mover, rope.refactor.move.MoveGlobal):
            return self._move_global(destination)
        if isinstance(self.mover, rope.refactor.move.MoveModule):
            return self._move_module(destination)
        if isinstance(self.mover, rope.refactor.move.MoveMethod):
            return self._move_method(destination)

    def _move_global(self, dest):
        destination = self.project.pycore.find_module(dest)
        return self.mover.get_changes(destination)

    def _move_method(self, dest):
        return self.mover.get_changes(dest, self.mover.get_method_name())

    def _move_module(self, dest):
        destination = self.project.pycore.find_module(dest)
        return self.mover.get_changes(destination)

    def _get_confs(self):
        if isinstance(self.mover, rope.refactor.move.MoveGlobal):
            prompt = 'Destination module: '
        if isinstance(self.mover, rope.refactor.move.MoveModule):
            prompt = 'Destination package: '
        if isinstance(self.mover, rope.refactor.move.MoveMethod):
            prompt = 'Destination attribute: '
        return {'destination': config.Data(prompt)}


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

    def _calculate_changes(self, values):
        return self.packager.get_changes()


class Inline(Refactoring):

    name = 'inline'
    key = 'C-c r i'
    saveall = False
    optionals = {'remove': config.Data('Remove the definition: ',
                                       values=['yes', 'no'])}

    def _create_refactoring(self):
        self.inliner = rope.refactor.inline.create_inline(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values):
        remove = values.get('remove', 'yes') == 'yes'
        return self.inliner.get_changes(remove=remove)


class ExtractVariable(Refactoring):

    name = 'extract_variable'
    key = 'C-c r l'
    saveall = False
    confs = {'name': config.Data('Extracted variable name: ')}

    def _create_refactoring(self):
        start, end = self.region
        self.extractor = rope.refactor.extract.ExtractVariable(
            self.project, self.resource, start, end)

    def _calculate_changes(self, values):
        return self.extractor.get_changes(values['name'])


class ExtractMethod(Refactoring):

    name = 'extract_method'
    key = 'C-c r m'
    saveall = False
    confs = {'name': config.Data('Extracted method name: ')}

    def _create_refactoring(self):
        start, end = self.region
        self.extractor = rope.refactor.extract.ExtractMethod(
            self.project, self.resource, start, end)

    def _calculate_changes(self, values):
        return self.extractor.get_changes(values['name'])


class OrganizeImports(Refactoring):

    name = 'organize_imports'
    key = 'C-c i o'
    saveall = False

    def _create_refactoring(self):
        self.organizer = rope.refactor.ImportOrganizer(self.project)

    def _calculate_changes(self, values):
        return self.organizer.organize_imports(self.resource)


class _GenerateElement(Refactoring):

    def _create_refactoring(self):
        kind = self.name.split('_')[-1]
        self.generator = rope.contrib.generate.create_generate(
            kind, self.project, self.resource, self.offset)

    def _calculate_changes(self, values):
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
