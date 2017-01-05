from .redisrwlock import RwlockClient
from . import __version__
import getopt
import logging
import logging.config
import os
import sys
import time


def logging_config():  # pragma: no cover
    dirs = [
        os.curdir,
        os.path.expanduser('~'),
        '/etc'
    ]
    done = False
    for loc in dirs:
        try:
            logging.config.fileConfig(
                os.path.join(loc, 'logging.conf'),
                disable_existing_loggers=False)
            done = True
            break
        except:
            pass
    if not done:
        config = dict(
            version=1,
            formatters={
                'f': {'format': '%(asctime)s (%(levelname).1s) %(message)s'}
            },
            handlers={
                'h': {'class': 'logging.StreamHandler',
                      'formatter': 'f',
                      'level': logging.DEBUG,
                      'stream': sys.stdout}
            },
            root={
                'handlers': ['h'],
                'level': logging.DEBUG
            },
            disable_existing_loggers=False
        )
        logging.config.dictConfig(config)


logging_config()
logger = logging.getLogger(__name__)


def usage():  # pragma: no cover
    print("Usage: %s -m %s [option] ..." % (sys.executable, __package__))
    print("")
    print("Options:")
    print("  -h, --help      print this help message and exit")
    print("  -V, --version   print version and exit")
    print("  -r, --repeat    repeat gc in every 5 seconds (Control-C to quit)")
    print("                  if not specified, just gc one time and exit")


def version():  # pragma: no cover
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("%s %s from %s (python %s)" % (
        __package__, __version__, pkg_dir, sys.version[:3]))


def main():  # pragma: no cover
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "hVr",
            ["help", "version", "repeat"])
    except getopt.GetoptError as err:
        print(err)
        sys.exit(1)
    opt_repeat = False
    for opt, opt_arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-V", "--version"):
            version()
            sys.exit()
        elif opt in ("-r", "--repeat"):
            opt_repeat = True
        else:
            assert False, "unhandled option"  # pragma: no cover
    # Gc periodically
    client = RwlockClient()
    while True:
        logger.info('redisrwlock gc')
        client.gc()
        if not opt_repeat:
            break
        time.sleep(5)


if __name__ == '__main__':
    main()
