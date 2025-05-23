from .DosLibrary import DosLibrary
from .ExecLibrary import ExecLibrary
from .GraphicsLibrary import GraphicsLibrary
from .IntuitionLibrary import IntuitionLibrary
from .LocaleLibrary import LocaleLibrary
from .MathFFPLibrary import MathFFPLibrary
from .MathIEEEDoubBasLibrary import MathIEEEDoubBasLibrary
from .MathIEEEDoubTransLibrary import MathIEEEDoubTransLibrary
from .MathIEEESingBasLibrary import MathIEEESingBasLibrary
from .MathIEEESingTransLibrary import MathIEEESingTransLibrary
from .MathTransLibrary import MathTransLibrary
from .TimerDevice import TimerDevice
from .UtilityLibrary import UtilityLibrary
from .VamosTestDevice import VamosTestDevice
from .VamosTestLibrary import VamosTestLibrary

vamos_libs = {
    "dos.library": DosLibrary,
    "exec.library": ExecLibrary,
    "graphics.library": GraphicsLibrary,
    "intuition.library": IntuitionLibrary,
    "locale.library": LocaleLibrary,
    "mathffp.library": MathFFPLibrary,
    "mathieeedoubbas.library": MathIEEEDoubBasLibrary,
    "mathieeedoubtrans.library": MathIEEEDoubTransLibrary,
    "mathieeesingbas.library": MathIEEESingBasLibrary,
    "mathieeesingtrans.library": MathIEEESingTransLibrary,
    "mathtrans.library": MathTransLibrary,
    "timer.device": TimerDevice,
    "utility.library": UtilityLibrary,
    "vamostestdev.device": VamosTestDevice,
    "vamostest.library": VamosTestLibrary,
}
