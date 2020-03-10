"""support functions for handling key-value parameters"""


def parse_key_value_string(s, d):
    """parse a single key=value string and add it to the given dictionary"""
    pos = s.find("=")
    if pos == -1:
        d[s] = True
    else:
        key = s[:pos]
        value = s[pos + 1 :]
        v = value.lower()
        if v in ("true", "on"):
            value = True
        elif v in ("false", "off"):
            value = False
        elif v.startswith("0x"):
            value = int(v[2:], 16)
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


def parse_keys_values_in_string(s):
    """parse key1=value1,key2=value2,..."""
    return parse_key_value_strings(s.split(","))


def parse_name_args_string(s):
    """parse name:key1=value,... and return name,args_dict"""
    pos = s.find(":")
    if pos == -1:
        return s, {}
    name = s[:pos]
    args = parse_keys_values_in_string(s[pos + 1 :])
    return name, args
