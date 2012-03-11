import re

tag = "$VER:"

def find(data):
  off = data.find(tag)
  if off == -1:
    return None
  start = off + len(tag)
  end = start
  size = len(data)
  while end < size:
    if data[end] == chr(0):
      break
    end += 1
  return data[start:end].strip()
  
def get_version(str):
  m = re.search('\s(\d+)\.(\d+)\s', str)
  if m == None:
    return None
  else:
    return (int(m.group(1)), int(m.group(2)))
