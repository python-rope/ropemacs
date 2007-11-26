class Data(object):

    def __init__(self, prompt=None, default=None,
                 values=None, starting=None):
        self.prompt = prompt
        self.default = default
        self.values = values
        self.starting = starting


def show_dialog(askdata, actions, confs={}, optionals={}):
    result = {}
    for name, conf in confs.items():
        result[name] = askdata(conf)
    names = list(confs.keys())
    names.extend(optionals.keys())
    names.extend(actions)
    base_question = Data('Choose what to do? ',
                         default=actions[0], values=names)
    while True:
        response = askdata(base_question)
        if response == '':
            response = base_question.default
        if response in actions:
            break
        else:
            if response in confs:
                conf = confs[response]
            else:
                conf = optionals[response]
            result[response] = askdata(conf)
    return response, result
