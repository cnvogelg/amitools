.. highlight :: text

#######
xdftool
#######

*the universal Amiga disk image file tool*

************
Introduction
************

The ``xdftool`` is a tool from the amitools tool set that allows to read disk
images intended for Amiga emulators like ADF or HDF files and display or
extract their contents. Furthermore, you can

* create new ADF or HDF images
* copy files from the image
* copy your own files to it
* master own images
* repack existing images
* work on partitions inside RDISK/RDB hdf images or on real disks

*****
Usage
*****

``xdftool`` is a command line utility that is always called with an image file
path name as the first argument and with one or more commands working on this
image::

  > xdftool <image.adf|image.hdf> <command> [option]

You can issue multiple commands on a single image by concatenating them with
a plus character::

  > xdftool <image.[ah]df> <command1> [options1] + <command2> [options2] ...

For Example:::

  > xdftool test.adf format ``My Image`` + makedir c + write myfile c

********
Commands
********

This section describes the commands available for ``xdftool``.
You can always issue a ``help`` command to see all commands::

  > xdftool test.adf help


Inspect Image
=============

``list`` - Display the list of files
------------------------------------

::

  list [<ami_path>] [all] [info] [detail]

This command lists the given directory in the image.

The ``info`` option appends some statistics information at the end of the list
including used blocks, bytes and file bytes. Each file or directory is display
with name, size, protection flags, modification date and comment (if
available).

The ``detail`` options replaces the comment with details on the file``s storage
including number of data blocks and file system blocks.

The ``all`` option shows a directory recursively, i.e. also its contained
directories.

If no ``<ami_path>`` is given then the full contents of the volume contained
in the image will be listed. This implies the ``all`` and ``info`` options.

Example:::

  > xdftool test.adf list         ; show whole image
  > xdftool test.adf list /       ; same command
  > xdftool test.adf list c all   ; show 'C' directory on image


``type`` - Display the contents of a file
-----------------------------------------

::

  type <ami_path>

The contents of the specified Amiga file will be written to the standard
output. This is useful to quickly see the contents of a file in an image.

Example::

  > xdftool wb310.adf type s/startup-sequence
  > xdftool pics.adf type mycool.ilbm | ilbmtoppm > img.ppm


``info`` - Disk Image Information
---------------------------------

::

  info

Display information on the disk image. This will display the number of blocks
totally available in the disk image, the number of used and free blocks.
Additionally, the corresponding byte values are printed.

Example::

  > xdftool wb310.adf info
  Blocks:   total:     1760   used:     1698  free:       62
  Bytes:    total:   901120   used:   869376  free:    31744


``read`` - Read file data or directory tree from an Image
---------------------------------------------------------

::

  read <ami_path> [sys_path]

If ``<ami_path>`` is a file then the file contents will be read and copied to
your hosts file system. If no ``<sys_path>`` is given then the Amiga file will
be written to the host's current directory with the base name of the
``<ami_path>``.  If the ``<sys_path>`` is given and is a directory then the
file will be written there. Otherwise the ``<syspath>`` is the file name for
the host file.

If the ``<ami_path>`` is a directory then the full directory structure
including files and sub directories will be transferred to the host's file
system. If no ``<sys_path>`` is given then the directory tree will be created
in host's current directory. If ``<sys_path>`` is available then the directory
will be created in this path. Otherwise the directory will be named as
``<sys_path>``.

Example::

  > xdftool wb310.adf read c/dir     ; copy file 'dir' to host's current dir
  > xdftool wb310.adf read c/dir .   ; same command
  > xdftool wb310.adf read c/dir a   ; copy file 'dir' to host file 'a'
  > xdftool wb310.adf read devs      ; copy 'devs' dir tree to current dir
  > xdftool wb310.adf read devs .    ; same command
  > xdftool wb310.adf read devs b    ; copy dir tree 'devs' to host dir 'b'


``blkdev`` - Show information on the underlying block device
------------------------------------------------------------

::

  blkdev

Displays the number of cylinders, heads, and sectors available in the image``s
block device


``open`` - Open existing image for processing
---------------------------------------------

::

  open [part=<name|number>] [chs=<cyls>,<heads>,<secs>] [h=<heads>] [s=<secs>]

This command opens an existing image for further processing. This is typically
the first command in a command list as it allows all other commands to work on
the selected file system.

Most often you do not need to specify this command as it will be automatically
prepended if its missing. In this case all parameters for opening the input
disk image are determined automatically.

If the parameters can't be detected or you don't want to use the detected
values then you specify the ``open`` command explicetly.

The ``part`` option is useful if you access a RDISK or RDB hdf image. In this
case the image holds a full disk with multiple partitions. ``xdftool`` can
only work on a single partition or file system and thus you must select which
partition to work on. You can either give a number selecting the ``n``-th
partition (startin with ``0``, of course!) or give the device name associated
with this partition (e.g. ``dh0``) without the colon.

The ``chs`` or ``h`` and ``s`` options are useful for HDF images without RDB
to describe the disk geometry. ``xdftool`` has an algorithm to determine the
disk geometry automatically from the byte size, but this approach might fail
for some setups. In this case you can either fully specify the disk geometry
with the ``chs`` option or guide the detection algorithm by giving a sector
``s`` and/or heads ``h`` value.

Example::

  > xdftool mydisk.rdisk open part=dh1 + list  ; open partition 'dh1:' in image
  > xdftool disk.hdf open chs=10,1,32 + list   ; open image with given geometry
  > xdftool disk.hdf open h=5 s=16 + list      ; guide auto detection


Edit Image
==========

``create`` - Create a new image file
------------------------------------

::

  create [ size=<size> [h=<heads>] [s=<secs>] | chs=<cyls>,<heads>,<secs> ]

With this command you can create a new disk image file. If the disk image
format has a fixed size (e.g. ADF) then you do not need to specify extra
paramters to this command.

For a hard disk image (HDF) file you must either give the total ``size`` in
bytes or the disk geometry in cylinders, heads, and sectors. If you specify
only the size then the disk geometry will be automatically derived. You can
use the optional paramters ``h`` and/or ``s`` to fixate parts of the disk
geometry and guide the detection of the disk layout.

Please note that the create command only creates an empty disk image that is
not formatted yet. You will need the ``format`` command to create a valid
empty file system on it.

You can't create a RDB/RDISK image with this command. Use the ``rdbtool`` for
this task.

Example::

  > xdftool new.hdf create size=10Mi     ; create an empty HDF image with 10Mi
  > xdftool new.adf create               ; create an empty floppy disk image
  > xdftool new.hdf create chs=10,1,32   ; create disk with given geometry
  > xdftool new.hdf create size=10Mi h=2 ; force 2 heads


``format`` - Format an existing or create a new disk image
----------------------------------------------------------

::

  format <volume_name> [dostype] [<create options>]

A new and blank *OFS/FFS* file system will be created on the given image file.

.. warning::

  All data previously stored there will be lost!!!

The ``<volume_name>`` gives the name of the new file system. The optional
``dos_type`` gives the file system variant. Its the base type ``ofs`` or
``ffs`` combined with variant flags added with a plus ``+`` (and no spaces).
Or you give a ``DOSx`` type of the file system in the range of ``DOS0`` and
``DOS7``.

The following variant flags are recognized:

* ``intl`` for international mode.
* ``dc`` or ``dircache`` for directory caching
* ``ln`` or ``longname`` for long file name support

If the disk image file you specify does not exist on disk yet then an implicit
``create`` command will be executed first. If the file already exists you must
use the ``create`` command if you want to create a resized image.

Example::

  > xdftool empty.adf format 'My Empty Disk'   ; create a blank OFS disk image
  > xdftool empty.hdf format Work size=10M     ; create a 10M hdf image
  > xdftool empty.hdf format Work chs=640,1,32 ; create with given geometry
  > xdftool empty.hdf format Work size=10M ffs ; create an FFS hdf image
  > xdftool empty.hdf create size=10M + format Work ffs ; same result
  > xdftool empty.hdf format Work size=10M ffs+ln ; create with long name support


``boot`` - Alter the boot block
-------------------------------

::

  boot show [hex] [asm]
  boot read <file>
  boot write <file>
  boot install [boot1x]
  boot clear

This command allows to inspect and modify the boot block of a disk.

The ``show`` command displays the contents of the boot block. The ``hex`` and
``asm`` alloy you to add a hex dump display of the boot block and even a
disassembly. (This requires the ``vda68k`` disassembler in the current path)

The ``read`` command reads the boot code (if available) from the disk image and
stores it in the given host file. The ``write`` command allows you write back
boot code stored in a file to the disk image. The checksum of the block will
be adjusted automatically.

The ``install`` command allows to write a typical WB 2.x/3.x boot code to the
disk to make it bootable. If you specify the ``boot1x`` option then a WB 1.x
boot code will be written instead.

The ``clear`` command will remove the boot code from the boot block and
invalidates the checksum so that the disk is not bootable anymore.

Example::

  > xdftool my.adf boot show               ; show the boot block
  > xdftool my.adf boot read boot.code     ; read boot code from disk
  > xdftool my.adf boot write boot.code    ; write boot code back to disk
  > xdftool my.adf boot install            ; make disk bootable
  > xdftool my.adf boot clear              ; make disk not bootable anymore


``makedir`` - Create a new directory
------------------------------------

::

  makedir <ami_path>

This will create a new directory a the given ``<ami_path>``. Note that
all preceeding directories need to exist already otherwise an error will be
issued.

Example::

  > xdftool empty.adf makedir c      ; create a new directory called 'c'


``write`` - Write a host file or a host directory tree to the image
-------------------------------------------------------------------

::

  write <sys_path> [ami_path]

If the given ``<sys_path>`` is a file then the contents of the file will be
read and stored with the same name in the top-level directory of the image's
volume. If ``<ami_path>`` is specified then the file will be stored there. If
``<ami_path>`` is a directory then the file is placed there. Otherwise the
file will be renamed to the given name.

If the given ``<sys_path>`` is a directory then this directory including all
contained files will be transferred to the image. If ``<ami_path>`` is given
and a directory then the host directory will be created there. Otherise the
host directory will be renamed to the given name.

Example::

  > xdftool empty.adf write README      ; the host file 'README' is written to
                                        ; the volume's root directory
  > xdftool empty.adf write README /    ; same command
  > xdftool empty.adf write README c    ; write to 'c' directory (if exists)
                                        ; or rename to file 'c'
  > xdftool empty.adf write mydir       ; the host directory 'mydir' is written


``delete`` - Delete a file or directory
---------------------------------------

::

  delete <ami_path> [all] [wipe]

Delete the file or directory given with ``<ami_path>``.

If a directory is specified then it must be empty otherwise delete will fail.
If you specify ``all`` then the contents of a directory is deleted first and
it allows you to delete non-empty directory trees.

The ``wipe`` option ensures that all freed blocks in the delete operation are
erased with zero bytes.

Example::

  > xdftool mydisk.adf delete README    ; delete the 'README' file
  > xdftool mydisk.adf delete c/dir     ; delete file 'dir' in dir 'c'
  > xdftool mydisk.adf delete c         ; delete 'c' dir if its empty
  > xdftool mydisk.adf delete c all     ; delete 'c' including all contents


``protect`` - Change the protect flags of a file or directory
-------------------------------------------------------------

::

  protect <ami_path> [+/-]<flags>

This command alters the protect flags associated with the given
``<ami_path>``. The flags to be set are given with any combination of the
characters ``hsparwed``. You can prefix the flags with either ``+`` or ``-``
to add or remove flags from the current flag set. If no prefix is given then
the given flags erase the old ones.

Example::

  > xdftool mydisk.adf protect test rwe  ; set the flags 'rwe' to file 'test'
  > xdftool mydisk.adf protect test -w   ; remove the 'f' flag
  > xdftool mydisk.adf protect test +d   ; add the 'd' flag


``comment`` - Change the comment of a file or directory
-------------------------------------------------------

::

  comment <ami_path> <comment_string>

The given string ``<comment_string>`` will be written as a comment to the
given ``<ami_path>`` file or directory. If you want to clear the comment then
simply set an empty string.

Example::

  > xdftool mydisk.adf comment test 'what a nice comment' ; set a comment
  > xdftool mydisk.adf comment test ''  ; remove comment/set empty one


``time`` - Change the modification time of a file or directory
--------------------------------------------------------------

::

  time <ami_path> <time_string>

This command changes the modification time associated with the
given ``<ami_path>`` file or directory. The time string must have the following
notation (and needs to be quoted because of the contained spaces)::

  '06.07.1986 14:38:56.45'
  '06.07.1986 14:38:56'

The first notation allows to specify the number of ticks (1/50th s) in a time
stamp.

Example::

  > xdftool mydisk.adf time test '06.07.1986 14:38:56.45'
  > xdftool mydisk.adf time mydir '06.07.1986 14:38:56'


``relabel`` - Change the name of the volume
-------------------------------------------

::

  relabel <new_name>

Set a new name for the volume.

Example::

  > xdftool my.adf relabel 'A New Name'


``root`` - Change parameters of the root block
----------------------------------------------

::

  root show
  root create_time <time_string>
  root disk_time <time_string>
  root time <time_string>

This command set allows to show and alter the information stored in the root
block of the file system.

The ``show`` command displays the contents of the root block.

The ``create_time``, ``disk_time``, ``time`` sub commands allow you change the
volume``s creation, total disk and modification time respectively. All
commands require a valid time string (see ``time`` command above for details).

Example::

  > xdftool my.adf root show
  > xdftool my.adf root create_time '06.07.1986 14:38:56.45'
  > xdftool my.adf root disk_time '06.07.1986 14:38:56'
  > xdftool my.adf root time '06.07.1986 14:38:56.45'


Pack/Repack/Unpack Images
=========================

The ``xdftool`` provides advanced commands to convert the whole contents of a
disk image to a host file system and allows to later on reconstruct the image
from the files only.

Un/packing Explained
--------------------

**Unpacking** a disk image means that starting from the volume's root all
directories and files contained in the image will be extracted to the host
file system and the same directory tree will be recreated. The host file
system structure starts with a directory named after the volume.

The host file system now contains the directory tree with all files and
directories. The contents of the files is also readily available. What's
still missing are the meta infos available in the Amiga disk image but not
found in the host file system: protection flags, comments and modification
time in tick resolution.

These missing meta infos are stored in a MetaDB file called
``<volume>.xdfmeta``. In the header line meta infos of the volume are stored
including volume name, dos_type, and the root time stamps. Then for each file
of the image an entry line is created that states the file or directory name
followed by a colon and the meta infos: protection flags, modification time
stamp and comment.

If the disk image is bootable then a file called ``<volume>.bootcode`` is
created. This holds the boot code that is required to make the disk bootable
again.

Finally, for HDF images a file called ``<volume>.blkdev`` is created that
holds the disk geometry of the original HDF file. The file only contains the
values ``<cylinder>,<heads>,<sectors>``.

With the volume's directory tree, the meta info DB and optional bootcode and
blkdev files in place you have everything on your host file system to allow
the exact recreation of an disk image later on. This recreation is called
**packing** in xdftool.

You can also use packing to **master** Amiga disk images: Simply create a
volume directory tree on your host file system and call ``xdftool``'s pack
command to create an image file from it. If you want to adjust the meta infos
then add a .xdfmeta MetaDB file and everything will be set as needed on
packing.

**Repacking** allows you to combine the unpacking and repacking operations
in one step. The command is useful to defragment and rebuild the whole file
system in a new image with the exact same contents. It is also possible to
create a new image with different size in the pack step. This allows you to
expand or shrink the image.


``unpack`` - Extract a disk image to the host``s file system
------------------------------------------------------------

::

  unpack <sys_dir> [fsuae]

The disk image volume's directory tree will be completely extracted to the
host file system at ``<sys_dir>``. First a directory with the volume's name is
created and inside all files and directories of the image.

Furthermore, a MetaDB file called ``<volume_name>.xdfmeta`` is created right
next to the volume's directory. This file stores all meta infos from the
volume and the contained files.

A ``<volume_name>.bootcode`` file is created if the disk image is bootable. A
``<volume_name>.blkdev`` file is created to store the disk geometry of disk
image's block device.

If ``fsuae`` option is given then the meta data of each file is written to
a FS-UAE compatible ``.uaem`` file right next to the original file. Use this
option if you want to use the unpacked directory as a volume inside FS-UAE.

Example::

  > xdftool mydisk.adf unpack .   ; unpack full image to current directory
  > xdftool mydisk.hdf unpack .   ; same for hard disk images
  > xdftool mydisk.hdf unpack .  fsuae  ; store meta info in .uaem files


``pack`` - Create a disk image from host files
----------------------------------------------

::

  pack <volume_dir> [blkdev_size]

If you have unpacked a disk image then you can pack it again with
this command. Simply specify the volume's directory. Note: All data available
in the disk image will be lost and overwritten!!!

If a MetaDB called ``<volume_dir>.xdfmeta`` exists then the files in the
images will be created with correct protection flags, modification time and
comment.

Pack automatically detects if a FS-UAE meta file with ``.uaem`` extension is
available and then extracts the file's meta info there.

If a boot code file called ``<volume_dir>.bootcode`` is available then this
code is written to the image``s boot block and made bootable.

If a HDF image will be packed then the block device must be specified either
by specifying ``blkdev_size`` (e.g. ``10M`` or ``640,1,32`` see ``format``
command) or a file called ``<volume_dir>.blkdev`` must be available with
cylinder, heads, sectors settings.

Example::

  > xdftool newimg.adf pack WB3.1  ; pack a disk image from host dir 'WB3.1'
  > xdftool newimg.hdf pack Dir 10M ; pack host dir 'Dir' into a 10M HD image


``repack`` - Repack the contents of one image into another one
--------------------------------------------------------------

::

  repack <src_img.[ah]df> [<open options>]

This command allows you to rebuild an existing disk image by combining the
``unpack`` and ``pack`` commands on the fly without creating a host file
system representation.

This command is very useful to better *stuff* and *de-fragment* data on a file
system that already performed lots of delete and create operations.

You always specify the image from which you want to import. The target image
is the image you specify on the ``xdftool`` command line.

If you are repacking from a HDF image then you can add options like to the
``open`` command to specify the disk geometry or the partition in a RDB image.
If nothing is specified then the target size is taken from the source size.

You can prepend a ``create`` command to repack a HDF to another sized HDF.

Example::

  > xdftool new.adf repack old.adf            ; repack 'old.adf' into 'new.adf'
  > xdftool new.hdf repack old.hdf chs=10,2,32; repack 'old.hdf' with given geo
  > xdftool new.hdf create size=10M + repack old.hdf ; repack to larger disk
  > xdftool new.hdf repack old.rdisk part=dh0 ; repack one partition of a disk


Low-Level Commands
==================

``xdftool`` also provides a set of low-level commands that let you look into
details of the file system to better understand its inner workings. These
commands are suitable for experts only.

``bitmap`` - Inspect the block allocation bitmap of the file system
-------------------------------------------------------------------

::

  bitmap info
  bitmap free [brief]
  bitmap used [brief]
  bitmap find [n]
  bitmap all [brief]
  bitmap maps [brief]
  bitmap root [brief]
  bitmap node <ami_path> [all] [entries] [brief]

The ``info`` command calculates the free and used blocks.

The ``free`` and ``used`` commands show the unallocated/allocated blocks on
the disk. Use the ``brief`` option to show only bitmap lines with contents.

The ``find`` command calls the block allocator and tells you what would be the
next free block on the disk. Give a number ``n`` to reserve a sequence of
blocks.

The ``all`` command shows all allocations in the bitmap. ``maps`` shows the
blocks allocated by the bitmap itself. ``root`` gives the root block.

The ``node`` command requires an ``<ami_path>`` on the image and shows the
blocks allocated for the given file or directory. If a directory is specified
and the ``all`` option is given then all blocks occupied by files and sub dirs
are also shown. If the ``entries`` option is given then a directory and its
entries are shown.

The bitmap output used different characters to code the block meaning:

``.``
  no information available

``x``
  reserved blocks

``F``
  unallocated/free block

``#``
  allocated/used block

``V``
  volume dir/root block

``R``
  root block

``D``
  directory header block

``C``
  directory cache block

``H``
  file header block

``d``
  file data block

``E``
  file extension block

``b``
  bitmap block

``B``
  bitmap extension block

Example::

  > xdftool test.adf bitmap free brief
  > xdftool test.adf bitmap used
  > xdftool test.adf bitmap find 10
  > xdftool test.adf bitmap all
  > xdftool test.adf bitmap node C entries brief


``block`` - Show blocks of the file system
------------------------------------------

::

  block boot
  block root
  block node <ami_path> [data]
  block dump <block_no>

The ``boot`` and ``root`` sub commands simply show the boot and root block
(similar to ``boot show`` and ``root show`` commands above).

The ``node`` sub command requires an <ami_path> and shows all blocks
associated with this file or directory. If ``data`` option is given then also
data blocks of a file are included in the display. Otherwise only structure
blocks are shown.

The ``dump`` command requires a block number and simply gives a hex dump of
the block``s data

Example::

  > xdftool test.adf block boot
  > xdftool test.adf block root
  > xdftool test.adf block node c
  > xdftool test.adf block node myfile data
  > xdftool test.adf block dump 880
