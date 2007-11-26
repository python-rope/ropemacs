import unittest

from ropemacs import config


class ConfigTest(unittest.TestCase):

    def setUp(self):
        super(ConfigTest, self).setUp()

    def tearDown(self):
        super(ConfigTest, self).tearDown()

    def test_trivial_case(self):
        action, confs = config.show_dialog(_MockAskConfig(['done']), ['done'])
        self.assertEquals('done', action)
        self.assertEquals({}, confs)

    def test_asking_normal_configs(self):
        confs = {'name': config.Data()}
        minibuffer = _MockAskConfig(['value', 'done'])
        action, result = config.show_dialog(minibuffer,
                                            ['done', 'cancel'], confs)
        self.assertEquals({'name': 'value'}, result)
        self.assertEquals('done', action)

    def test_optional_confs(self):
        optionals = {'name': config.Data()}
        minibuffer = _MockAskConfig(['done'])
        action, result = config.show_dialog(minibuffer, ['done', 'cancel'],
                                            optionals=optionals)
        self.assertEquals(None, result.get('name', None))
        self.assertEquals('done', action)

    def test_optional_confs2(self):
        optionals = {'name': config.Data()}
        minibuffer = _MockAskConfig(['name', 'value', 'done'])
        action, result = config.show_dialog(minibuffer, ['done', 'cancel'],
                                            optionals=optionals)
        self.assertEquals({'name': 'value'}, result)
        self.assertEquals('done', action)


class _MockAskConfig(object):

    def __init__(self, responses=[]):
        self.responses = responses
        self.asked = []

    def __call__(self, config):
        self.asked.append(config)
        return self.responses[len(self.asked) - 1]


if __name__ == '__main__':
    unittest.main()
