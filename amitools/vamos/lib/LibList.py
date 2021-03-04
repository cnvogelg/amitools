from .DosLibrary import DosLibrary
from .ExecLibrary import ExecLibrary
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
from .VamosTestLibrary import VamosTestLibrary
from .VamosTestDevice import VamosTestDevice

vamos_libs = {
    "dos.library": DosLibrary,
    "exec.library": ExecLibrary,
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
    "vamostest.library": VamosTestLibrary,
    "vamostestdev.device": VamosTestDevice,
}
