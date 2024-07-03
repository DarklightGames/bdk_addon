def radians_to_unreal(value: float) -> int:
    return int(value * 10430.378350470452724949566316381)


def unreal_to_radians(value: int) -> float:
    return float(value) / 10430.378350470452724949566316381


def meters_to_unreal(value: float) -> float:
    return value * 60.352
