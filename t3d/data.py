from collections import OrderedDict


class T3DActor(OrderedDict):
    def __init__(self, class_: str, name: str):
        super().__init__()
        self['Class'] = class_
        self['Name'] = name


class T3DMap:
    def __init__(self):
        self.actors = []
