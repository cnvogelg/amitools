from amitools.vamos.cfgcore import Argument, Parser, Value


def parse_display_scale(value):
    parts = str(value).lower().split("x")
    if len(parts) == 1:
        parts *= 2
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ValueError("display scale must be N or XxY, e.g. 2 or 1x2")
    scale = tuple(int(part) for part in parts)
    if any(not 1 <= component <= 8 for component in scale):
        raise ValueError("display scale components must be between 1 and 8")
    return scale


class DisplayParser(Parser):
    def __init__(self):
        super().__init__(
            "display",
            {
                "display": {
                    "scale": "1",
                    "aspect": Value(str, "square", enum=("square", "4:3")),
                }
            },
            {
                "display": {
                    "scale": Argument(
                        "--display-scale",
                        action="store",
                        help="SDL window scale: N or XxY (1..8)",
                    ),
                    "aspect": Argument(
                        "--display-aspect",
                        action="store",
                        help="pixel presentation: square or 4:3",
                    ),
                }
            },
            "display",
            "host display options",
            {"display": {"scale": "scale", "aspect": "aspect"}},
            "display",
        )
