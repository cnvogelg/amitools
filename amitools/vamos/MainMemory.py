from Exceptions import *
from AccessMemory import AccessMemory

# MainMemory manages the whole address map of the CPU
# Its divided up into pages of 64K
# So every address can be written as:
#
# xxyyyy -> page xx offset yyyy

class MainMemory:
  def __init__(self, raw_mem, label_mgr):
    self.access = AccessMemory(raw_mem, label_mgr)
