#-*- coding: utf-8 -*-

from lib2to3.fixer_base import BaseFix


class FixHasattrimfunc(BaseFix):

    PATTERN = """\
power< 'hasattr' trailer< '(' arglist< any ',' name="'im_func'"> ')' > > any*
"""

    def transform(self, node, results):
        name = results['name']
        name.value = "'__func__'"
        name.changed()


