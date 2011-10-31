import logging
import logging.config

# --- vamos loggers ---

log_main = logging.getLogger('main')

log_mem = logging.getLogger('mem')
log_mem_init = logging.getLogger('mem_init')
log_mem_alloc = logging.getLogger('mem_alloc')
log_mem_int = logging.getLogger('mem_int')

log_lib = logging.getLogger('lib')
log_res = logging.getLogger('res')

log_path = logging.getLogger('path')
log_file = logging.getLogger('file')
log_lock = logging.getLogger('lock')

log_dos  = logging.getLogger('dos')
log_exec = logging.getLogger('exec')

loggers = [log_main, log_mem, log_mem_init, log_mem_alloc, log_mem_int, log_lib, log_path, log_file, log_lock, log_res, log_dos, log_exec]

# --- end ---

OFF = 100
levels = {
  "debug" : logging.DEBUG,
  "info" : logging.INFO,
  "warn" : logging.WARN,
  "error" : logging.ERROR,
  "fatal" : logging.FATAL,
  "off" : OFF
}

def log_parse_level(name):
  if levels.has_key(name):
    return levels[name]
  else:
    return None

def log_setup(arg,verbose=False,quiet=False):
  # setup handler
  ch = logging.StreamHandler()
  ch.setLevel(logging.DEBUG)
  # and formatter
  formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(name)10s:%(levelname)7s:  %(message)s', datefmt='%H:%M:%S')
  ch.setFormatter(formatter)
  for l in loggers:
    l.addHandler(ch)
  
  # setup default
  level = logging.WARN
  if quiet:
    level = OFF
  for l in loggers:
    l.setLevel(level)
  
  # is verbose enabled?
  if verbose:
    log_main.setLevel(logging.INFO)
  
  # parse args
  if arg != None:
    kvs = arg.split(',')  
    for kv in kvs:
      name,level_name = kv.lower().split(':')
      level = log_parse_level(level_name)
      if level == None:
        raise ValueError("Invalid logging level %s" % level_name)
      if name == 'all':
        for l in loggers:
          l.setLevel(level)
      else:
        found = False
        for l in loggers:
          if l.name == name:
            l.setLevel(level)
            found = True
            break
        if not found:
          raise ValueError("Invalid logging channel %s" % name)
