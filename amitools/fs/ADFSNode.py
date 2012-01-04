class ADFSNode:
  def __init__(self, volume, block, hash_idx):
    self.volume = volume
    self.block = block
    self.hash_idx = hash_idx
    self.name = block.name

  