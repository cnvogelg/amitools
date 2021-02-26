#######
rdbtool
#######

*the universal Amiga disk partition tool*

************
Introduction
************

The ``rdbtool`` is a tool from the amitools tool set that allows to inspect or
create hard disk partitions readable by the classic Amiga family of computers.
The *RDB* or *Rigid Disk Block* is a format to describe the first blocks of a
hard disk that store information of partitions and file systems used in the
partitions.

If you want to work with files stored in the DOS file system of a partition
then have a look at the :doc:`xdftool` of amitools.

*****
Usage
*****

Disk Image Files
================

rdbtool is a command line utility that is always called with an hard disk
image file path name as the first argument and with one or more commands
working on this image::

  > rdbtool <image.rdb|image.rdisk> <command> [option]

You can issue multiple commands on a single image by concatenating them with
a plus character::

  > rdbtool <image.rdb> <command1> [options1] + <command2> [options2] ...

For example::

  > rdbtool myimg.rdb create size=10Mi + init + fill

Most options in rdbtool are given as ``key=value`` pairs. Here the option
``size`` is given with value ``10Mi`` for a 10 MiB sized disk image.

Real Block Device
=================

On Unix/Linux/macOS you can also use a block device of a real hard disk or a
CF/SD flash card to directly work on a real device. The file names for the
block device differ on the different platforms but typical names are
``/dev/rdisk1`` or ``/dev/sda``.

Always make sure to select the block device of the whole drive (e.g.
``/dev/hdc``) and not the device of some already existing paritioning (e.g.
``/dev/hdc1``).

.. warning::

  Also make sure (really, really sure!) to select the correct block device of
  the hard disk you want to alter with ``rdbtool``. Otherwise you might
  destroy your actual system disk!!! Most OSes need a priviliged user to
  perform these operations so you need to run ``rdbtool`` as ``root`` or with
  ``sudo`` in this case.


********
Commands
********

This section describes the commands available for rdbtool. You can always
issue a ``help`` command to see all commands::

  > rdbtool test.img help


Open/Create an Image
====================

In rdbtool there are two ways to access an image: open or create it. The
``open`` operation assumes that the disk image file already exists or is used
for existing devices available through block device names.


``create`` - Create a new disk image
------------------------------------

::

  create [ size=<size> | chs=<cyl>,<heads>,<secs> | from=<img> ] [ bs=<n> ]

The ``create`` operation is used to create a new image file. The create
command needs a size parameter::

  > rdbtool test.img create size=10Mi

You can either specify the total size in bytes (or here with unis *M=mega
Mi=Ki-Units*) and let rdbtool choose a suitable disk geometry automatically or
you can give the geometry with::

  > rdbtool test.img create chs=10,1,32

Here 10 cylinders, 1 head and 32 sectors are defined.

Another way to specify the size of the new image is to give the file name
of an existing image or real device. This is useful to create a new image
of compatible size::

  > rbdtool test.img create from=other.img

You can only use the ``create`` command if the given image file does not exist
yet. If it already exists then an error message is generated. However, you can
*force* the creation of the image file by giving the ``-f`` switch for force::

  > rdbtool -f test.img create chs=10,1,32

By default a disk layout with a block size of 512 bytes is created. For larger
disks you may want to increase the block size to 1024, 2048, or 4096. Use the
``bs``` option to select the block size::

  > rdbtool create size=32Gi bs=4096

.. note:: Amigas only support RDBs with a 512 byte block size!


``open`` - Open existing image for processing
---------------------------------------------

::

  open [ chs=<cyl>,<heads>,<secs> | c=<cyl> h=<heads> s=<secs> ] [ bs=<n> ]

The open operation usually does not need any paramters::

  > rdbtool test.img open + info

You can even omit the ``open`` command before other commands in this case::

  > rdbtool test.img info

This will implicitly open the image first.

If no option is given then the disk geometry is automatically determined from
the image size. If this does not work for an image you can also specify the
geometry of the image in the open command::

  > rdbtool test.img open chs=10,1,32

You can also only hint the geometry by giving some geometry paramters and let
rdbtool guess the others::

  > rdbtool test.img open c=10 h=2 s=32

By default the block size of the disk is assumed to be 512. If an RDB is
already stored on the disk then ``rdbtool`` automatically retrieves the block
size from there. You can force a block size by giving the ``bs`` option with
the ``open`` command. This is useful if you want to overwrite an existing RDB
with a different block size on a disk::

  > rdbtool /dev/disk1 open bs=4096 + init

.. note:: Amigas only support RDBs with a 512 byte block size!


``resize`` - Change size of existing image
---------------------------------------------

::

  resize [ chs=<cyl>,<heads>,<secs> | c=<cyl> h=<heads> s=<secs> | from=<img> ] [ bs=<n> ]

Similar to the ``create`` command you can specify the new size of an image.
It will be either shrunk or grown.

.. note:: 

  The RDB that may be already on the disk is not touched or adjusted!
  Use the ``adjust`` command to adjust the RDB as well.


Inspect the Partition Layout
============================

``info`` - Show information of the RDB data structures
------------------------------------------------------

::

  info [partition]

This command gives an overview of the partitions and file systems stored in
the RDB blocks. It will return something like::

  PhysicalDisk:               0     7817     7880544  3.8Gi  heads=16 sectors=63
  LogicalDisk:                2     7817     7878528  3.8Gi  rdb_blks=[0:2015,60(60)] cyl_blks=1008
  Partition: #0 'CDH0'        2      103      102816   50Mi    1.31%  DOS3 bootable pri=0
  Partition: #1 'DH0'       104      205      102816   50Mi    1.31%  DOS3
  Partition: #2 'DH1'       206     2035     1844640  900Mi   23.41%  DOS3
  Partition: #3 'DH2'      2036     3763     1741824  850Mi   22.11%  DOS3
  Partition: #4 'DH3'      3764     3909      147168   71Mi    1.87%  DOS3
  Partition: #5 'CDH1'     3910     3971       62496   30Mi    0.79%  DOS3
  Partition: #6 'DH4'      3972     4124      154224   75Mi    1.96%  DOS3
  Partition: #7 'DH5'      4125     5953     1843632  900Mi   23.40%  DOS3
  Partition: #8 'DH6'      5954     7817     1878912  917Mi   23.85%  DOS3
  FileSystem #0                                              DOS1 version=40.1 size=24588

If a partition name (.e.g ``DH0``) or index (e.g. ``3``) is given then only
the information for a single partition is displayed::

  > rdbtool test.hdf info DH0
  Partition: #1 'DH0'       104      205      102816   50Mi    1.31%  DOS3

``show`` - Show internal block representation of the RDB data structures
------------------------------------------------------------------------

::

  show

This command is a low-level tool that shows the blocks available in the RDB
data structure with their corresponding values. Use this to debug or analyze
issues with complex RDBs.


Create a new RDB
================

``init`` - Create a new and empty RDB structure
-----------------------------------------------

::

  init [ rdb_cyls=<cyls> ]

This command creates a new and initially empty RDB structure.

.. warning:

  Any existing  partitioning layout will be lost after executing this command!
  So you have been warned!

Call this command first to start building a new RDB structure on a disk or
disk image::

  > rdbtool test.img create size=10Mi + init

The default RDB occupies all the sectors of the first cylinder. If you have
chosen a geometry with small cylinders then a single cylinder might not be
sufficient to hold the RDB data structures. In this case use the ``rdb_cyls``
option to set the number of cylinders to reserve for RDB::

  > rdbtool test.img create size=10Mi + init rdb_cyls=2


``adjust`` - Adjust range of existing RDB structure
---------------------------------------------------

::

  adjust ( auto [ force ] | [ lo=<cyl> ] [ hi=<cyl> ] [ phys ] )

This command changes the range on the disk that the current RDB covers.
It is very handy if you copy a pre-existing image file to a real medium
(e.g. compact flash card) with a larger size.

You can either use the ``auto`` mode that automatically increases the RDB
range to cover the full image or medium. If the cylinder number gets too
large then you need to add the ``force`` option to allow the change.

  > rdbtool /dev/disk4 adjust auto

In manual mode you have to specify the new range of the RDB by giving either
the ``lo`` and/or ``hi`` cylinder. If you add the ``phys`` option then 
not only the logical range of the RDB will be changed but also its
physical extend.

  > rdbtool test.img adjust hi=1000 phys

The ``adjust`` command will abort with an error if the existing partitions
do not fit into the new range.


``remap`` - Change geometry of existing RDB structure
-----------------------------------------------------

::

  remap [ s=<sectors> ] [ h=<heads> ]

This command allows to change the interal geometry of the disk image.
The geometry consists of cylinders, heads, and sectors. Typically, the
number of heads and sectors is chosen in such a way that the number
of cylinders spanning the image does not grow too large.

If you want to ``adjust`` an RDB to a larger device size then the cylinder
ranges might get too large. In this case use the ``remap`` command first
to increase the sectors and/or heads to keep the cylinders in a reasonable
range.

  > rdbtool image.rdb remap s=32 h=8

Note that the ``remap`` operation is only allowed if the physical and logical
disk layout can be converted to the new values without any resizing. 
Additionally, all partition ranges must be mappable as well.


``add`` - Add a new partition
-----------------------------

::

  add  <size> [ name=<name> ] [ dostype|fs=<dostag> ]
              [ bootable[=true|false] ] [ pri=<priority> ]
              [ automount=true|false ] [ bs=<n> ]

This command creates a new partition.

You have to give the size of the partition in one of the following ways:

1. Give start and end cylinder::

    start=<cyl> end=<cyl>

2. Give start cylinder and size::

    start=<cyl> size=<cyl|percent|bytes>

3. Only give size::

    size=<cyl|percent|bytes>

For the size you can specify a number of cylinders, a percent value, or a byte
size (The percent value gives the ratio of the total logical disk size)::

  > rdbtool test.img add start=2 end=5	; give start and end cylinder
  > rdbtool test.img add start=4 size=10  ; give start and number of cylinders
  > rdbtool test.img add size=10MiB       ; give size in bytes
  > rdbtool test.img add size=50%         ; use half the disk size

If no ``name`` option is given then the defaul name ``DH`` is used appended
with the current partition number starting with 0: ``DH0, DH1``. You can alter
the base name by giving the ``-p`` switch (for drive prefix)::

  > rdbtool -p CH test.img init + add size=10%   ; create partition CH0

The ``dostype`` or ``fs`` switch can be used to select the file system you
will use to format the partition. The default is ``DOS3``, i.e. Fast Filing
System with International Support. You can give the dostype with ``DOS<n>`` or
as a hex number ``0x44556677`` or for standard DOS file systems with ``ofs``,
``ffs`` and append ``dc`` or ``dircache`` or ``intl`` flags::

  dostype=DOS0        ; OFS
  dostype=ofs+dc      ; OFS + dircache
  dostype=ffs+intl    ; FFS + international mode
  dostype=0x44556677  ; give hex of dostype

You can make a partition bootable by setting the ``bootable`` flag.
Additionally you can select the boot priority with ``pri=<n>``::

  > rdbtool test.img add size=10% bootable pri=10

The ``bs`` option allows you to specify the block size of the file system.
By default ``rdbtool`` uses the block size of the RDB parition itself, e.g.
512. The file system block size must be a multiple of the parition block
size, e.g. 1024, 2048, 4096, or 8192.


``addimg`` - Add a new partition from an image file
---------------------------------------------------

::

  addimg <file> [ start=<cyl> ]
                [ name=<name> ] [ dostype|fs=<dostag> ]
                [ bootable[=true|false] ] [ pri=<priority> ]
                [ automount=true|false ] [ bs=<n> ]

This command creates a new partition from the contents of a given partition
image file. The size of the partition is automatically derived from the file
size. The start of the partition is either given with the ``start`` option
or selected automatically from the next free range in the partition table. 

Note that the image size must be a multiple of the cylinder size. Otherwise
the partition can't be added.

The ``dostype`` is automatically derived from the first four bytes of the
image file. The file system block size can't be detected automatically and
must be given with the ``bs`` option if a non-standard (512 bytes) size is
used.

See the ``add`` command for an explanation of the other options.


``change`` - Modify parameters of an existing partition
-------------------------------------------------------

::

  change <id>  [ name=<name> ] [ dostype|fs=<dostag> ]
               [ bootable[=true|false] ] [ pri=<priority> ]
               [ automount=true|false ] [ bs=<n> ]

The ``<id>`` is the number of the paritition as given in the ``info`` command.
You can also use the device name to select a partition::

  > rdbtool test.img change 0 name=CH0 bootable=true

For options see the ``add`` command.


``free`` - Show free cylinder range in partition layout
-------------------------------------------------------

::

  free

This command returns one or more cylinder ranges that are currently not
occupied by partitions. You can use this command to find out the range for a
new partition.

If the current partition layout aready occupies the whole disk then this
command will return nothing.


``fill`` - Fill the remaining space in the partition layout
-----------------------------------------------------------

::

  fill [ name=<name> ] [ dostype|fs=<dostag> ]
       [ bootable[=true|false] ] [ pri=<priority> ]
       [ automount=true|false ] [ bs=<n> ]

This command takes the free space in a partition layout and creates a new
partition that fills this space.

This command supports the same options as used in the ``add`` command above.

If multiple holes are in the current partition layout then this command
creates a new partition for each existing hole.

With this command you can easily finish paritioning without the need of
calculating the size of the final partition::

  # create 2 partitions with 50% size each
  > rdbtool test.img init + add size=50% + fill
  > rdbtool test.img init + add size=10% + add size=20% + fill

For options see the ``add`` command.


``delete`` - Delete an existing partition
-----------------------------------------

::

  delete  <id>

This command removes an existing partition and frees all associated resources.

The ``<id>`` is the number of the paritition as given in the ``info`` command.
You can also use the device name to select a parition::

  > rdbtool mydisk.rdb delete 0
  > rdbtool mydisk.rdb delete dh1


``map`` - Show the allocation map of the RDB blocks
---------------------------------------------------

::

  map

This command lets you look under the hood of the RDB. It will print all blocks
associated with the RDB and shows their current contents. A two char code is
used for each block::

  --    block is empty and not used for RDB
  RD    the main rigid disk block
  P?    partition <n>
  F?    file system <n>

Example::

  > rdbtool mydisk.rdb map


Import/Export Partitions
========================

``export`` - Export Data of a Partition into a File
---------------------------------------------------

::

  export <partition> <file_name>

Store the raw byte contents of a partition into the given file.
As a result a file system image will be written. You can use the result
as a RDB-less image in ``xdftool``.


``import`` - Import Data from a File into a Partition
-----------------------------------------------------

::

  import <partition> <file_name>

Read the raw partition data from a given file into an existing partition.
You typically use a RDB-less file system image as input.


Working with File System Drivers
================================

The RDB data structure allows to store file system drivers for classic
AmigaOS, so the Kickstart can load the driver before mounting a parition in
the RDB.

File systems are LoadSeg()able Amiga Hunk binaries directly embedded in the
RDB blocks.

Use the ``info`` command to see if any file systems are already stored in the
RDB. In the output you can see that the file systems are numbered in rdbtool
starting with 0.


``fsget`` - Retrieve the file system driver from a RDB structure
----------------------------------------------------------------

::

  fsget  <id> <filename>

This command extracts the file system numbered ``<id>`` and stores the
LoadSeg()able Amiga binary on your local system into a new file with the given
``<filename>``::

  # create a new file "ffs" with the first driver
  > rdbtool mydisk.rdb fsget 0 ffs


``fsadd`` - Add a new file system driver
----------------------------------------

::

  fsadd  <filename>  [version=<x.y>]

Add the LoadSeg()able file system driver stored in file ``<filename>`` to the
current RDB.

Every file system driver needs a version information given as ``<x>.<y>``,
e.g. ``40.63``. When a file is loaded the version is automatically extracted
from a ``VER:`` tag inside the binary. If this tag cannot be found you can
specify the version with the ``version`` option::

  > rdbtool mydisk.rdb fsadd ffs version=60.32


``fsflags`` - Change flags of file system
-----------------------------------------

::

  fsflags  <id>  [ clear | key=value ... ]

With this command you can alter the device node flags of a file system.

The file system ``<id>`` is the number of the file system as listed with the
``info`` command.

The following keys are supported::

  type
  task
  lock
  handler
  stack_size
  priority
  startup
  seg_list_blk
  global_vec

The ``clear`` option will remove all flags first. All other commands add the
corresponding flag::

  > rdbtool mydisk.rdb fsflags 0 clear stack_size=8192

Have a look at the output of the ``info`` command to see the flags set for a
file system.


``fsdelete`` - Remove a file system
-----------------------------------

::

  fsdelete <id>

The file system with the given number is removed. All associated blocks of the
file system are free'd in the RDB structure.
