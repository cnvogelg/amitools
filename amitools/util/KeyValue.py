"""support functions for handling key-value parameters"""

def parse_key_value_string(s, d):
  """parse a single key=value string and add it to the given dictionary"""
  pos = s.find('=')
  if pos == -1:
    d[s] = True
  else:
    key = s[:pos]
    value = s[pos+1:]
    v = value.lower()
    if v in ("true","on"):
      value = True
    elif v in ("false","off"):
      value = False
    else:
      # try a value
      try:
        value = int(value)
      except ValueError:
        pass
    d[key] = value

def parse_key_value_strings(strs):
  """parse an array of strings with key=value contents and create a dictionary from it."""
  result = {}
  for s in strs:
    parse_key_value_string(s, result)
  return result

