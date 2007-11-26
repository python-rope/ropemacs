import ropemacs
from ropemacs import config
import rope.refactor.rename


class Refactoring(object):

    name = None
    key = None
    confs = None
    optionals = None
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
            lisp.message('Cancelled!')
            return
        changes = self._calculate_changes(result)
        self._perform(changes)

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

    def _perform(self, changes):
        self.interface._perform(changes)

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
