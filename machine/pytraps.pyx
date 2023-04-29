# traps.h
cdef extern from "traps.h":
  int TRAP_DEFAULT
  int TRAP_AUTO_RTS
  int TRAP_ONE_SHOT
  ctypedef void (*trap_func_t)(uint opcode, uint pc, void *data)
  void trap_init()
  int  trap_setup(trap_func_t func, int flags, void *data)
  void trap_free(int id)
  int trap_aline(uint opcode, uint pc)

cdef object trap_exc_func

from cpython.exc cimport PyErr_Print

cdef void trap_wrapper(uint opcode, uint pc, void *data):
  cdef object py_func = <object>data
  try:
    py_func(opcode, pc)
  except:
    if trap_exc_func is not None:
      trap_exc_func(opcode, pc)
    else:
      raise

cdef class Traps:
  cdef dict func_map

  def __cinit__(self):
    trap_init()
    self.func_map = {}

  def cleanup(self):
    self.set_exc_func(None)

  def set_exc_func(self, func):
    global trap_exc_func
    trap_exc_func = func

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

  def trigger(self, uint opcode, uint pc):
    return trap_aline(opcode, pc)

  def get_func(self, tid):
    if tid in self.func_map:
      return self.func_map[tid]

