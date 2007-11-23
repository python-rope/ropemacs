class Config(object):

    def __init__(self, name):
        self.name = name


def ask(confs, minibuffer):
    result = {}
    for conf in confs:
        result[conf.name] = minibuffer(conf.name)
    return result
