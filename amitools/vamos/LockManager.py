from Log import log_lock

class LockManager:
  def __init__(self, path_mgr, base_addr):
    self.path_mgr = path_mgr
    self.base_addr = base_addr
    log_lock.info("init manager: base=%06x" % self.base_addr)