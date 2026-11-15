import pytest

from amitools.vamos.cfg import VamosMainParser
from amitools.vamos.cfg.display import parse_display_scale
from amitools.vamos.lib.IntuitionLibrary import IntuitionLibrary


def cfg_display_cli_and_ini_test():
    parser = VamosMainParser()
    assert parser.parse(
        args=["--display-scale", "2", "--display-aspect", "4:3", "test"]
    )
    assert parser.get_display_dict().display == {"scale": "2", "aspect": "4:3"}
    parser.parse_dict_config({"display": {"scale": "1x2", "aspect": "square"}}, "ini")
    assert parse_display_scale(parser.get_display_dict().display.scale) == (1, 2)


@pytest.mark.parametrize("value", ["0", "2x0", "9", "1x2x3", "nan", "-1", "2.5"])
def cfg_display_reject_invalid_scale_test(value):
    with pytest.raises(ValueError):
        parse_display_scale(value)


def intuition_display_aspect_and_mouse_test():
    lib = IntuitionLibrary()
    lib.display_scale = (2, 2)
    assert lib._display_size(640, 256) == (1280, 512)
    lib.display_aspect = "4:3"
    assert lib._display_size(640, 256) == (1280, 960)
    assert lib._display_size(640, 200) == (1280, 960)
    lib._window_scales[7] = (2, 3.75)
    assert lib._guest_mouse(640, 480, 7) == (320, 128)
    assert lib._guest_mouse(1279, 959, 7) == (639, 255)
