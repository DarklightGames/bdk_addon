import re
from typing import Iterable


def auto_increment_name(name, names: Iterable[str]):
    while name in names:
        match = re.match(r'(.+)\.(\d+)', name)
        if match:
            name = match.group(1)
            number = int(match.group(2)) + 1
        else:
            number = 1
        name = f'{name}.{number:03d}'
    return name
