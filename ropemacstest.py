import unittest

from ropemacs import config


class ConfigTest(unittest.TestCase):

    def setUp(self):
        super(ConfigTest, self).setUp()

    def tearDown(self):
        super(ConfigTest, self).tearDown()

    def test_trivial_case(self):
        config.ask([], MiniBuffer())

    def test_asking_normal_configs(self):
        confs = [config.Config('name')]
        minibuffer = MiniBuffer(['value'])
        result = config.ask(confs, minibuffer)
        self.assertEquals(['name'], minibuffer.asked)
        self.assertEquals({'name': 'value'}, result)


class MiniBuffer(object):

    def __init__(self, responses=[]):
        self.responses = responses
        self.asked = []

    def __call__(self, message):
        self.asked.append(message)
        return self.responses[len(self.asked) - 1]


if __name__ == '__main__':
    unittest.main()
