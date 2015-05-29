# traps.h
cdef extern from "traps.h":
  int TRAP_DEFAULT
  int TRAP_AUTO_RTS
  int TRAP_ONE_SHOT
  ctypedef unsigned int uint
  ctypedef void (*trap_func_t)(uint opcode, uint pc, void *data) except *
  void trap_init()
  int  trap_setup(trap_func_t func, int flags, void *data)
  void trap_free(int id)

cdef void trap_wrapper(uint opcode, uint pc, void *data) except *:
  cdef object py_func = <object>data;
  py_func(opcode, pc)

cdef class Traps:
  cdef dict func_map

  def __cinit__(self):
    trap_init()
    self.func_map = {}

  def setup(self, py_func, auto_rts=False, one_shot=False):
    cdef int flags
    flags = TRAP_DEFAULT
    if auto_rts:
      flags |= TRAP_AUTO_RTS
    if one_shot:
      flags |= TRAP_ONE_SHOT
    tid = trap_setup(trap_wrapper, flags, <void *>py_func)
    if tid != -1:
      # keep function reference around
      self.func_map[tid] = py_func
    return tid

  def free(self, tid):
    trap_free(tid)
    del self.func_map[tid]
