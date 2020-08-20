TRUE_VALUES = ['true', 'True', '1', 'yes', True, 1]
FALSE_VALUES = ['false', 'False', '0', 'no', False, 0]


def str_or_bool(value):
    if value in TRUE_VALUES:
        value = True
    elif value in FALSE_VALUES:
        value = False
    return value
