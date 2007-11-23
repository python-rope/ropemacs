class Config(object):

    def __init__(self, name, prompt=None, values=None):
        self.name = name
        self.prompt = prompt
        self.values = values


def ask(confs, askconfig):
    result = {}
    for conf in confs:
        result[conf.name] = askconfig(conf)
    return result
