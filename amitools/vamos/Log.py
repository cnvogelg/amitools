import logging
import logging.config

# --- vamos loggers ---

log_main = logging.getLogger('main')

log_mem = logging.getLogger('mem')
log_mem_init = logging.getLogger('mem_init')
log_mem_alloc = logging.getLogger('mem_alloc')
log_mem_int = logging.getLogger('mem_int')
log_instr = logging.getLogger('instr')

log_lib = logging.getLogger('lib')
log_libmgr = logging.getLogger('libmgr')
log_res = logging.getLogger('res')

log_path = logging.getLogger('path')
log_file = logging.getLogger('file')
log_lock = logging.getLogger('lock')
log_doslist = logging.getLogger('doslist')

log_dos  = logging.getLogger('dos')
log_exec = logging.getLogger('exec')
log_utility = logging.getLogger('utility')

log_proc = logging.getLogger('proc')
log_prof = logging.getLogger('prof')

log_tp = logging.getLogger('tp')
log_hw = logging.getLogger('hw')

loggers = [
  log_main, log_mem, log_mem_init, log_mem_alloc, log_mem_int,
  log_instr, log_lib, log_libmgr, log_path, log_file, log_lock,
  log_doslist, log_res, log_dos, log_exec, log_proc, log_prof,
  log_tp, log_utility, log_hw
]

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

def log_help():
  print "logging channels:"
  names = map(lambda x: x.name, loggers)
  for n in sorted(names):
    print "  %s" % n
  print
  print "logging levels:"
  for l in levels:
    print "  %s" % l

def log_setup(arg=None, verbose=False, quiet=False, log_file=None):
  # setup handler
  if log_file != None:
    ch = logging.FileHandler(log_file, mode='w')
  else:
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
    level = logging.ERROR
  for l in loggers:
    l.setLevel(level)

  # special default for profiling
  log_prof.setLevel(logging.INFO)

  # is verbose enabled?
  if verbose:
    log_main.setLevel(logging.INFO)

  # parse args
  if arg != None:
    kvs = arg.split(',')
    for kv in kvs:
      if kv.find(':') == -1:
        return False
      else:
        name,level_name = kv.lower().split(':')
        level = log_parse_level(level_name)
        if level == None:
          return False
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
            return False

  return True
