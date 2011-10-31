from LabelRange import LabelRange

class PortManager(LabelRange):
  def __init__(self, addr, size):
    LabelRange.__init__(self, "ports", addr, size)
    self.ports = {}
    self.base_addr = addr
    self.size = size
    self.cur_addr = addr
  
  def add_int_port(self, handler):
    addr = self.cur_addr
    self.cur_addr += 4
    port = {
      'addr' : addr,
      'handler' : handler,
      'queue' : None
    }
    self.ports[addr] = port
    return addr
    
  def add_port(self, addr):
    port = {
      'addr' : addr,
      'handler' : None,
      'queue' : []
    }
    self.ports[addr] = port
  
  def has_port(self, addr):
    return self.ports.has_key(addr)
  
  def rem_port(self, addr):
    del self.ports[addr]
  
  def put_msg(self, port_addr, msg_addr):
    port = self.ports[port_addr]
    handler = port['handler']
    # directly call handler to process message
    if handler != None:
      handler.put_msg(self, msg_addr)
    # enqueue message for later get_msg from code
    else:
      port['queue'].append(msg_addr)
  
  def has_msg(self, port_addr):
    port = self.ports[port_addr]
    queue = port['queue']
    return len(queue) > 0
  
  def get_msg(self, port_addr):
    port = self.ports[port_addr]
    queue = port['queue']
    if len(queue) == 0:
      return None
    else:
      return queue.pop(0)

    