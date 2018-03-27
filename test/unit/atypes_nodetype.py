import pytest
from amitools.vamos.atypes import NodeType

def libnative_node_type_to_str_test():
  assert NodeType.to_str(NodeType.NT_UNKNOWN) == 'NT_UNKNOWN'
  with pytest.raises(ValueError):
    NodeType.to_str(-1)

def libnative_node_type_from_str_test():
  assert NodeType.from_str('NT_INTERRUPT') == NodeType.NT_INTERRUPT
  with pytest.raises(ValueError):
    NodeType.from_str('bla')
