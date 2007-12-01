class Data(object):

    def __init__(self, prompt=None, default=None, values=None, kind=None):
        self.prompt = prompt
        self.default = default
        self.values = values
        self.kind = kind


def show_dialog(askdata, actions, confs={}, optionals={}):
    result = {}
    for name, conf in confs.items():
        result[name] = askdata(conf)
    actions.append('batchset')
    names = list(confs.keys())
    names.extend(optionals.keys())
    names.extend(actions)
    base_question = Data('Choose what to do: ',
                         default=actions[0], values=names)
    batchset_question = Data('Batch sets: ')
    while True:
        response = askdata(base_question)
        if response == '':
            response = base_question.default
        elif response == 'batchset':
            sets = askdata(batchset_question)
            for key, value in _parse_batchset(sets).items():
                result[key] = value
        elif response in actions:
            break
        else:
            if response in confs:
                conf = confs[response]
            else:
                conf = optionals[response]
            oldvalue = result.get(response, None)
            result[response] = askdata(conf, starting=oldvalue)
    return response, result


def _parse_batchset(sets):
    result = []
    multiline = False
    for line in sets.splitlines(True):
        if line[0].isspace() and multiline:
            result[-1][1] += line[1:]
        else:
            if not line:
                continue
            multiline= False
            tokens = line.split(None, 1)
            value = ''
            if len(tokens) > 1:
                result.append([tokens[0], tokens[1].rstrip('\r\n')])
            else:
                multiline = True
                result.append([tokens[0], ''])
    return dict(result)
