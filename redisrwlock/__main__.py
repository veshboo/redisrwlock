from .redisrwlock import RwlockClient
from . import __version__
from redis import StrictRedis
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
    print("Usage: %s -m %s [option] ..." %
          (os.path.basename(sys.executable), __package__))
    print("")
    print("""\
Options:
  -h, --help      print this help message and exit
  -V, --version   print version and exit
  -r, --repeat    repeat gc periodically (Control-C to quit)
                  if not specified, just gc one time and exit
  -i, --interval  interval of the periodic gc in seconds (default 5)
  -s, --server    redis-server host to connect (default localhost)
  -p, --port      redis-server port to connect (default 6379)
""")


def version():  # pragma: no cover
    pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print("%s %s from %s (python %s)" % (
        __package__, __version__, pkg_dir, sys.version[:3]))


def main():  # pragma: no cover
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "hVri:s:p:",
            ["help", "version", "repeat", "interval=", "server=", "port="])
    except getopt.GetoptError as err:
        print("ERROR:", err)
        sys.exit(os.EX_USAGE)
    # Defaults
    opt_repeat = False
    opt_interval = 5
    opt_server = "localhost"
    opt_port = 6379
    for opt, opt_arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-V", "--version"):
            version()
            sys.exit()
        elif opt in ("-r", "--repeat"):
            opt_repeat = True
        elif opt in ("-i", "--interval"):
            try:
                opt_interval = int(opt_arg)
            except:
                print("ERROR: specify interval as number of seconds")
                sys.exit(os.EX_USAGE)
        elif opt in ("-s", "--server"):
            opt_server = opt_arg
        elif opt in ("-p", "--port"):
            try:
                opt_port = int(opt_arg)
            except:
                print("ERROR: specify port as number")
                sys.exit(os.EX_USAGE)
            pass
        else:  # pragma: no cover
            print("ERROR: unhandled option")
            sys.exit(os.EX_USAGE)
    # Gc periodically
    client = RwlockClient(StrictRedis(host=opt_server, port=opt_port))
    while True:
        logger.info('redisrwlock gc')
        client.gc()
        if not opt_repeat:
            break
        time.sleep(opt_interval)


if __name__ == '__main__':
    main()
