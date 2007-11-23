import unittest

from ropemacs import config


class ConfigTest(unittest.TestCase):

    def setUp(self):
        super(ConfigTest, self).setUp()

    def tearDown(self):
        super(ConfigTest, self).tearDown()

    def test_trivial_case(self):
        config.ask([], _MockAskConfig())

    def test_asking_normal_configs(self):
        confs = [config.Config('name')]
        minibuffer = _MockAskConfig(['value'])
        result = config.ask(confs, minibuffer)
        self.assertEquals(['name'], minibuffer.asked)
        self.assertEquals({'name': 'value'}, result)


class _MockAskConfig(object):

    def __init__(self, responses=[]):
        self.responses = responses
        self.asked = []

    def __call__(self, config):
        self.asked.append(config.name)
        return self.responses[len(self.asked) - 1]


if __name__ == '__main__':
    unittest.main()
