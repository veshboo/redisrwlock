from redisrwlock import RwlockClient
import unittest
import redis
import subprocess


#
# Test helpers
#


_REDIS_READY_MESSAGE = 'ready to accept connections on port '


def runRedisServer(port=6379):
    """runs redis-server"""
    # waits until it can accept client connection by reading its all
    # startup messages until it says 'ready to accept ...', then
    # redirect any following output to DEVNULL.
    port = str(port)
    server = subprocess.Popen(['redis-server', '--port', port],
                              stdout=subprocess.PIPE,
                              universal_newlines=True)
    message = _REDIS_READY_MESSAGE + port
    while message not in server.stdout.readline():
        pass
    dumper = subprocess.Popen(['cat'],
                              stdin=server.stdout,
                              stdout=subprocess.DEVNULL)
    return server, dumper


def terminateRedisServer(server, dumper):
    server.stdout.close()
    server.terminate()
    dumper.terminate()


_UNNEATY_AFTER_TEST = '!!! SOME REDISRWLOCK KEYS REMAIN AFTER TEST !!!'


def cleanUpRedisKeys():
    if RwlockClient()._clear_all():
        print(_UNNEATY_AFTER_TEST)  # pragma: no cover


class TestRedisRwlock_connection(unittest.TestCase):

    def setUp(self):
        self.server, self.dumper = runRedisServer(port=7777)

    def tearDown(self):
        terminateRedisServer(self.server, self.dumper)

    def test_RwlockClient_redis_connection(self):
        """
        test RwlockClient with non-default redis connection
        """
        client = RwlockClient(redis=redis.StrictRedis(port=7777))
        self.assertIsNotNone(client)
