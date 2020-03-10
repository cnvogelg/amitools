# Logging.py
#
# helper for logging

import logging

FORMAT = "%(asctime)-15s  %(levelname)-10s  %(name)-10s  %(message)s"


def add_logging_options(parser):
    """add logging options (-v, -q, -L) to an argparse"""
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="be more verbose"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", default=False, help="be totally quiet"
    )
    parser.add_argument(
        "-L", "--log-file", default=None, help="write tool output to log file"
    )


def setup_logging(opts):
    # setup level
    if opts.quiet:
        level = 100
    elif opts.log_file is not None:
        level = logging.DEBUG
    else:
        v = opts.verbose
        if v == 0:
            level = logging.WARNING
        elif v == 1:
            level = logging.INFO
        else:
            level = logging.DEBUG
    # setup logging
    logging.basicConfig(format=FORMAT, filename=opts.log_file, level=level)
