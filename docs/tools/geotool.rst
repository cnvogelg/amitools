#######
geotool
#######

*detect and compute disk geometries (cylinders, heads, sectors) for image files and sizes*

************
Introduction
************

The ``geotool`` computes a disk geometry -- the number of cylinders, heads and
sectors per track -- for a given image file or a raw byte size. It is mainly a
helper for creating and opening hard disk images: the geometry is the same one
``rdbtool`` and ``xdftool`` use when they build or read a hardfile.

The tool can detect the geometry from an existing image, set it up from
explicit options, or open and create block devices through the same factory the
other tools use.

*****
Usage
*****

::

  geotool (detect <size|file> [options] | setup <options> |
           open <file> [options] | create <file> <options>)

The geometry options are:

* ``size=<size>`` -- a byte size, e.g. ``20M``
* ``chs=<n>,<n>,<n>`` -- cylinders, heads, sectors per track
* ``c=<n>``, ``h=<n>``, ``s=<n>`` -- the same three values individually
* ``algo=1|2`` -- select the detection algorithm

********
Commands
********

``detect``
  Detect the geometry from an existing image file or from a byte size string::

    > geotool detect work.hdf
    > geotool detect 100M

``setup``
  Compute a geometry purely from the given options::

    > geotool setup size=20M algo=1
    > geotool setup c=100 h=16 s=63

``open``
  Open an existing image through the block device factory and print the class
  and geometry it reports::

    > geotool open work.hdf

``create``
  Create a new block device with a geometry computed from the options::

    > geotool create new.hdf size=20M

Each command prints the resolved geometry or ``FAILED`` if no geometry could be
determined.
