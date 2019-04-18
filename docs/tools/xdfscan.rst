#######
xdfscan
#######

*scanner to validate AmigaOS file systems in disk or hard disk images*

************
Introduction
************

I wrote this tool to inspect the large collection of disk (.adf) and hard disk
images I gathered over the years. The scanner either runs directly on files or
on a directory. The latter mode of operation then scans the directory tree
recursively and checks all disk and hard disk images found there.

The scanner does an in-depth check of all structures used in the AmigaOS
OFS and FFS file system. If something does not fulfill the file system
specification then an error or warning is generated. Warnings are usually
tolerated when using this image in an emulator but errors might hint to
corrupt files on the disk.

Each scanned file results in a single line output that gives you a quick
overview of the errors and warnings found in the image (if any). You can
also enable the verbose mode. Then all errors and warnings are reported.

*****
Usage
*****

You can call xdfscan with a file or a directory::

  > xdfscan test.adf          # scan a single image file
  > xdfscan test.hdf          # scan a single hard disk image

  > xdfscan my_disks          # scan all adfs and hdfs found in
                              # the directory tree below "my_disks"

In directory scan mode you can limit the scan to either disk images or hard
disk images only by using -D (skip disks) or -H (skip hard disks)::

  > xdfscan -H my_disks       # only disk images and no hard disk images
  > xdfscan -D my_hdfs        # only hard disk images and no disk images

Normal output uses single lines and only reports the number of errors and
warnings that were found. If you enable verbose mode (-v) then the warnings
and errors are printed::

  > xdfscan -v my_disks       # show warning and error messages

The tool also generates debug and information messages while scanning an image.
You can show these if you set the message level with the -l option::

  > xdfscan -v -l0 my_disks   # show also debug and info messages
  > xdfscan -v -l1 my_disks   # show info messages (and warn, error)


**************
Scanner Output
**************

A typically scan run looks like this::

  > xdfscan .
        E069      NOK   ./bookdisk/amiga_listing_03_89.adf
            boot  ok   ./bookdisk/devpac.adf
                  ok   ./bookdisk/gfabasic3.adf
                  nofs  ./bookdisk/giana.adf
            boot  ok   ./bookdisk/mut_hwtuning_1_9.adf
  w001      boot NOK   ./bookdisk/reflections_animator.adf
                  ok   ./bookdisk/reflectionsv1_0.adf

On the right you can see the name of the image that was scanned.

The next column to the left gives you the total result of the scan operation
of the image:

* ``ok``: disk image has no errors and warnings
* ``NOK``: either errors or warnings were found in disk image
* ``nofs``: no OFS or FFS file system was found on the disk image.
  this is typically the case for custom track loader games.
  boot block is ok and bootable but no OFS/FFS root block is found.
* ``NDOS``: no valid DOS boot block was found

The third column either is empty or displays ``boot``. This row indicates if
the file system contains a bootable boot block.

The first two columns are empty or show the total number of warnings or errors
found in the image.

If you enable verbose output with ``-v`` then you can see warnings and error
messages like these::

  w001      boot NOK   ./bookdisk/reflections_animator.adf
  @000880:WARN :Root bitmap flag not valid (-1)
                  ok   ./bookdisk/reflectionsv1_0.adf
        E002 boot NOK   ./commercial_soft/PCLink/pclink.adf
          ERROR:Invalid bitmap allocation (@40: #0+40) blks [1282...1313] got=00000000 expect=00008000
          ERROR:Invalid bitmap allocation (@45: #0+45) blks [1442...1473] got=00000000 expect=80000000

The first entry in a warning or error message is the block number where the
error occurred. If the message does not relate directly to a block number
then the first column is omitted.
