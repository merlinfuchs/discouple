class CommandError(Exception):
    pass


class NotEnoughArguments(CommandError):
    def __init__(self, parameter):
        self.parameter = parameter


class ConverterFailed(CommandError):
    def __init__(self, parameter, value, error):
        self.parameter = parameter
        self.value = value
        self.error = error
