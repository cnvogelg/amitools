from .ADFSVolume import ADFSVolume
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory


class Repacker:
    def __init__(self, in_image_file, in_options=None):
        self.in_image_file = in_image_file
        self.in_options = in_options
        self.in_blkdev = None
        self.out_blkdev = None
        self.in_volume = None
        self.out_volume = None

    def create_in_blkdev(self):
        f = BlkDevFactory()
        self.in_blkdev = f.open(
            self.in_image_file, read_only=True, options=self.in_options
        )
        return self.in_blkdev

    def create_in_volume(self):
        if self.in_blkdev == None:
            return None
        self.in_volume = ADFSVolume(self.in_blkdev)
        self.in_volume.open()
        return self.in_volume

    def create_in(self):
        if self.create_in_blkdev() == None:
            return False
        if self.create_in_volume() == None:
            return False
        return True

    def create_out_blkdev(self, image_file, force=True, options=None):
        if self.in_blkdev == None:
            return None
        # clone geo from input
        if options == None:
            options = self.in_blkdev.get_options()
        f = BlkDevFactory()
        self.out_blkdev = f.create(image_file, force=force, options=options)
        return self.out_blkdev

    def create_out_volume(self, blkdev=None):
        if blkdev != None:
            self.out_blkdev = blkdev
        if self.out_blkdev == None:
            return None
        if self.in_volume == None:
            return None
        # clone input volume
        iv = self.in_volume
        name = iv.get_volume_name()
        dos_type = iv.get_dos_type()
        meta_info = iv.get_meta_info()
        boot_code = iv.get_boot_code()
        self.out_volume = ADFSVolume(self.out_blkdev)
        self.out_volume.create(
            name, meta_info=meta_info, dos_type=dos_type, boot_code=boot_code
        )
        return self.out_volume

    def repack(self):
        self.repack_node_dir(
            self.in_volume.get_root_dir(), self.out_volume.get_root_dir()
        )

    def repack_node_dir(self, in_root, out_root):
        entries = in_root.get_entries()
        for e in entries:
            self.repack_node(e, out_root)

    def repack_node(self, in_node, out_dir):
        name = in_node.get_file_name().get_name()
        meta_info = in_node.get_meta_info()
        # sub dir
        if in_node.is_dir():
            sub_dir = out_dir.create_dir(name, meta_info, False)
            for child in in_node.get_entries():
                self.repack_node(child, sub_dir)
            sub_dir.flush()
        # file
        elif in_node.is_file():
            data = in_node.get_file_data()
            out_file = out_dir.create_file(name, data, meta_info, False)
            out_file.flush()
        in_node.flush()
