import rope.base.change
import rope.base.exceptions
import rope.contrib.generate
import rope.refactor.extract
import rope.refactor.inline
import rope.refactor.method_object
import rope.refactor.move
import rope.refactor.rename
import rope.refactor.restructure
import rope.refactor.usefunction
import rope.refactor.introduce_factory

from ropemacs import dialog, lisputils


class Refactoring(object):
    key = None
    confs = {}
    optionals = {}
    saveall = True

    def __init__(self, interface):
        self.interface = interface

    def show(self, initial_asking=True):
        self.interface._check_project()
        self.interface._save_buffers(only_current=not self.saveall)
        self._create_refactoring()
        action, result = dialog.show_dialog(
            lisputils.askdata, ['perform', 'preview', 'cancel'],
            self._get_confs(), self._get_optionals(),
            initial_asking=initial_asking)
        if action == 'cancel':
            lisputils.message('Cancelled!')
            return
        def calculate(handle):
            return self._calculate_changes(result, handle)
        name = 'Calculating %s changes' % self.name
        changes = lisputils.runtask(calculate, name=name)
        if action == 'perform':
            self._perform(changes)
        if action == 'preview':
            if changes is not None:
                diffs = str(changes.get_description())
                lisputils.make_buffer('*rope-preview*', diffs, switch=True,
                                      modes=['diff'], window='current')
                if lisputils.yes_or_no('Do the changes? '):
                    self._perform(changes)
                else:
                    lisputils.message('Thrown away!')
                lisputils.hide_buffer('*rope-preview*', delete=False)
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

    @property
    def name(self):
        return refactoring_name(self.__class__)

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
            self.interface._reload_buffers(changes)
            self._done()
        lisputils.runtask(perform, 'Making %s changes' % self.name,
                          interrupts=False)
        lisputils.message(str(changes.description) + ' finished')

    def _get_confs(self):
        return self.confs

    def _get_optionals(self):
        return self.optionals


class Rename(Refactoring):
    key = 'r'
    optionals = {
        'docs': dialog.Data('Rename occurrences in comments and docs: ',
                            values=['yes', 'no'], default='yes'),
        'in_hierarchy': dialog.Data('Rename methods in class hierarchy: ',
                                    values=['yes', 'no'], default='no'),
        'resources': dialog.Data('Files to apply this refactoring on: '),
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
        resources = _resources(self.project, values.get('resources', None))
        kwds = {
            'docs': values.get('docs', 'yes') == 'yes',
            'unsure': (lambda occurrence: unsure),
            'resources': resources}
        if self.renamer.is_method():
            kwds['in_hierarchy'] = values.get('in_hierarchy', 'no') == 'yes'
        return self.renamer.get_changes(newname,
                                        task_handle=task_handle, **kwds)

    def _get_confs(self):
        oldname = str(self.renamer.get_old_name())
        return {'newname': dialog.Data('New name: ', default=oldname)}


class RenameCurrentModule(Rename):
    key = '1 r'
    offset = None


class Restructure(Refactoring):
    key = 'x'
    confs = {'pattern': dialog.Data('Restructuring pattern: '),
             'goal': dialog.Data('Restructuring goal: ')}
    optionals = {
        'args': dialog.Data('Arguments: '),
        'imports': dialog.Data('Imports: '),
        'resources': dialog.Data('Files to apply this restructuring: ')}

    def _calculate_changes(self, values, task_handle):
        args = {}
        for raw_check in values.get('args', '').split('\n'):
            if raw_check:
                key, value = raw_check.split(':', 1)
                args[key.strip()] = value.strip()
        imports = [line.strip()
                   for line in values.get('imports', '').split('\n')]
        resources = _resources(self.project, values.get('resources', None))
        restructuring = rope.refactor.restructure.Restructure(
            self.project, values['pattern'], values['goal'],
            args=args, imports=imports)
        return restructuring.get_changes(resources=resources,
                                         task_handle=task_handle)


class UseFunction(Refactoring):
    key = 'u'
    optionals = {
        'resources': dialog.Data('Files to apply this refactoring on: ')}

    def _create_refactoring(self):
        self.user = rope.refactor.usefunction.UseFunction(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        resources = _resources(self.project, values.get('resources', None))
        return self.user.get_changes(resources=resources,
                                     task_handle=task_handle)


class Move(Refactoring):
    key = 'v'
    optionals = {
        'resources': dialog.Data('Files to apply this refactoring on: ')}

    def _create_refactoring(self):
        self.mover = rope.refactor.move.create_move(self.project,
                                                    self.resource,
                                                    self.offset)

    def _calculate_changes(self, values, task_handle):
        destination = values['destination']
        resources = _resources(self.project, values.get('resources', None))
        if isinstance(self.mover, rope.refactor.move.MoveGlobal):
            return self._move_global(destination, resources, task_handle)
        if isinstance(self.mover, rope.refactor.move.MoveModule):
            return self._move_module(destination, resources, task_handle)
        if isinstance(self.mover, rope.refactor.move.MoveMethod):
            return self._move_method(destination, resources, task_handle)

    def _move_global(self, dest, resources, handle):
        destination = self.project.pycore.find_module(dest)
        return self.mover.get_changes(
            destination, resources=resources, task_handle=handle)

    def _move_method(self, dest, resources, handle):
        return self.mover.get_changes(
            dest, self.mover.get_method_name(),
            resources=resources, task_handle=handle)

    def _move_module(self, dest, resources, handle):
        destination = self.project.pycore.find_module(dest)
        return self.mover.get_changes(
            destination, resources=resources, task_handle=handle)

    def _get_confs(self):
        if isinstance(self.mover, rope.refactor.move.MoveGlobal):
            prompt = 'Destination module: '
        if isinstance(self.mover, rope.refactor.move.MoveModule):
            prompt = 'Destination package: '
        if isinstance(self.mover, rope.refactor.move.MoveMethod):
            prompt = 'Destination attribute: '
        return {'destination': dialog.Data(prompt)}


class MoveCurrentModule(Move):
    key = '1 v'
    offset = None


class ModuleToPackage(Refactoring):
    key = '1 p'
    saveall = False

    def _create_refactoring(self):
        self.packager = rope.refactor.ModuleToPackage(
            self.project, self.resource)

    def _calculate_changes(self, values, task_handle):
        return self.packager.get_changes()


class Inline(Refactoring):
    key = 'i'
    optionals = {
        'remove': dialog.Data('Remove the definition: ',
                              values=['yes', 'no'], default='yes'),
        'only_current': dialog.Data('Inline this occurrence only: ',
                                    values=['yes', 'no'], default='no'),
        'resources': dialog.Data('Files to apply this refactoring on: ')}

    def _create_refactoring(self):
        self.inliner = rope.refactor.inline.create_inline(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        remove = values.get('remove', 'yes') == 'yes'
        only_current = values.get('only_current', 'no') == 'yes'
        resources = _resources(self.project, values.get('resources'))
        return self.inliner.get_changes(
            remove=remove, only_current=only_current,
            resources=resources, task_handle=task_handle)


class _Extract(Refactoring):
    saveall = False
    optionals = {'similar': dialog.Data('Extract similar pieces: ',
                                        values=['yes', 'no'], default='yes'),
                 'global_': dialog.Data('Make global: ',
                                        values=['yes', 'no'], default='no')}
    kind = None
    constructor = None

    def _create_refactoring(self):
        start, end = self.region
        self.extractor = self.constructor(self.project,
                                          self.resource, start, end)

    def _calculate_changes(self, values, task_handle):
        similar = values.get('similar', 'yes') == 'yes'
        global_ = values.get('global_', 'no') == 'yes'
        return self.extractor.get_changes(values['name'], similar=similar,
                                          global_=global_)

    def _get_confs(self):
        return {'name': dialog.Data('Extracted %s name: ' % self.kind)}


class ExtractVariable(_Extract):
    key = 'l'
    kind = 'variable'
    constructor = rope.refactor.extract.ExtractVariable


class ExtractMethod(_Extract):
    key = 'm'
    kind = 'method'
    constructor = rope.refactor.extract.ExtractMethod


class OrganizeImports(Refactoring):
    key = 'o'
    saveall = False

    def _create_refactoring(self):
        self.organizer = rope.refactor.ImportOrganizer(self.project)

    def _calculate_changes(self, values, task_handle):
        return self.organizer.organize_imports(self.resource)


class MethodObject(Refactoring):
    saveall = False
    confs = {'classname': dialog.Data('New class name: ',
                                      default='_ExtractedClass')}

    def _create_refactoring(self):
        self.objecter = rope.refactor.method_object.MethodObject(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        classname = values.get('classname')
        return self.objecter.get_changes(classname)


class IntroduceFactory(Refactoring):
    saveall = True
    key = 'f'
    optionals = {'global_factory': dialog.Data(
            'Make global: ', values=['yes', 'no'], default='yes'),
                 'resources': dialog.Data('Files to apply this refactoring on: ')}

    def _create_refactoring(self):
        self.factory = rope.refactor.introduce_factory.IntroduceFactory(
            self.project, self.resource, self.offset)

    def _calculate_changes(self, values, task_handle):
        name = values.get('factory_name')
        global_ = values.get('global_factory', 'yes') == 'yes'
        resources = _resources(self.project, values.get('resources'))
        return self.factory.get_changes(name, global_factory=global_,
                                        resources=resources,
                                        task_handle=task_handle)

    def _get_confs(self):
        default = 'create_%s' % self.factory.old_name.lower()
        return {'factory_name': dialog.Data('Factory name: ', default)}


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
    key = 'n v'


class GenerateFunction(_GenerateElement):
    key = 'n f'


class GenerateClass(_GenerateElement):
    key = 'n c'


class GenerateModule(_GenerateElement):
    key = 'n m'


class GeneratePackage(_GenerateElement):
    key = 'n p'


def refactoring_name(refactoring):
    classname = refactoring.__name__
    result = []
    for c in classname:
        if result and c.isupper():
            result.append('_')
        result.append(c.lower())
    name = ''.join(result)
    return name

def _resources(project, text):
    if text is None or text.strip() == '':
        return None
    result = []
    for line in text.splitlines():
        try:
            if line.strip() != '':
                result.append(project.get_resource(line.strip()))
        except rope.base.exceptions.ResourceNotFoundError:
            pass
    return result
