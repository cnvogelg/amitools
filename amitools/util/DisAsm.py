import subprocess
import tempfile
import os

class DisAsm:
  def __init__(self, use_objdump = False, cpu = '68000'):
    self.use_objdump = use_objdump
    self.cpu = cpu
 
  def _parse_vda68k(self, lines):
    # parse output: split addr, raw words, and code
    result = []
    for l in lines:
      addr = int(l[0:8],16)
      word = map(lambda x: int(x,16),l[10:30].split())      
      code = l[30:]
      result.append((addr,word,code))
    return result
 
  def _parse_objdump(self, lines):
    result = []
    for l in lines[7:]:
      if not '...' in l:
        addr_str = l[:8].strip()
        word_str = l[9:26].split()
        code = l[26:]
      
        addr = int(addr_str,16)
        word = map(lambda x: int(x,16),word_str)
        result.append((addr,word,code))
    return result
 
  def disassemble(self, data, start=0):
    # write to temp file
    tmpname = tempfile.mktemp()
    out = file(tmpname,"wb")
    out.write(data)
    out.close()
    
    if self.use_objdump:
      cmd = ["m68k-elf-objdump","-D","-b","binary","-m",self.cpu,tmpname]
    else:
      cmd = ["vda68k",tmpname,str(start)]
    
    # call external disassembler
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    output = p.communicate()[0]
    os.remove(tmpname)
    lines = output.splitlines()
    
    if self.use_objdump:
      return self._parse_objdump(lines)
    else:
      return self._parse_vda68k(lines)

  def dump(self, code):
    for line in code:
      ops = map(lambda x : "%04x" % x, line[1])
      print "%08x:  %-20s  %s" % (line[0]," ".join(ops),line[2])
