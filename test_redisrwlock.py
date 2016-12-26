from redisrwlock import Rwlock, RwlockClient
from test_redisrwlock_connection import (
    runRedisServer, terminateRedisServer, cleanUpRedisKeys)

import unittest
import os
import subprocess
import time


# Gc test util, run gc with expected message output
def runGcExpect(message):
    gc = subprocess.Popen(['python3', 'redisrwlock.py'],
                          stdout=subprocess.PIPE,
                          universal_newlines=True)
    found = False
    for line in gc.stdout:
        if message in line:
            found = True
            break
    gc.stdout.close()
    gc.wait()
    return found


def setUpModule():
    global _server, _dumper
    _server, _dumper = runRedisServer()


def tearDownModule():
    global _server, _dumper
    terminateRedisServer(_server, _dumper)


class TestRedisRwlock(unittest.TestCase):

    def setUp(self):
        cleanUpRedisKeys()

    def tearDown(self):
        cleanUpRedisKeys()

    def test_lock(self):
        """
        test simple lock
        """
        client = RwlockClient()
        rwlock = client.lock('N1', Rwlock.READ)
        self.assertEqual(rwlock.status, Rwlock.OK)
        self.assertEqual(rwlock.name, 'N1')
        self.assertEqual(rwlock.mode, Rwlock.READ)
        self.assertEqual(rwlock.pid, str(os.getpid()))
        client.unlock(rwlock)

    def test_unlock(self):
        """
        test normal unlock after lock
        """
        client = RwlockClient()
        rwlock = client.lock('N1', Rwlock.READ)
        self.assertEqual(client.unlock(rwlock), True)

    def test_unlock_excessive(self):
        """
        test call unlock more than lock
        """
        client = RwlockClient()
        rwlock = client.lock('N1', Rwlock.READ)
        client.unlock(rwlock)
        self.assertEqual(client.unlock(rwlock), False)

    def test_lock_nesting(self):
        """
        test lock again for already owned one
        """
        client = RwlockClient()
        # R then R
        rwlock1 = client.lock('N1', Rwlock.READ)
        rwlock2 = client.lock('N1', Rwlock.READ)
        self.assertEqual(rwlock2.status, Rwlock.OK)
        self.assertEqual(rwlock2.name, 'N1')
        self.assertEqual(rwlock2.mode, Rwlock.READ)
        self.assertEqual(rwlock2.pid, rwlock1.pid)
        client.unlock(rwlock2)
        client.unlock(rwlock1)
        # R then W
        rwlock1 = client.lock('N2', Rwlock.READ)
        rwlock2 = client.lock('N2', Rwlock.WRITE)
        self.assertEqual(rwlock2.status, Rwlock.OK)
        self.assertEqual(rwlock2.name, 'N2')
        self.assertEqual(rwlock2.mode, Rwlock.WRITE)
        self.assertEqual(rwlock2.pid, rwlock1.pid)
        client.unlock(rwlock2)
        client.unlock(rwlock1)

    def test_lock_fail_nowait(self):
        """test lock fail with no wait"""
        # Simulate other process
        client1 = RwlockClient(pid=str(os.getpid() - 1))
        client2 = RwlockClient()
        rwlock1 = client1.lock('N1', Rwlock.READ)
        rwlock2 = client2.lock('N1', Rwlock.WRITE)
        self.assertEqual(rwlock2.status, Rwlock.FAIL)
        client1.unlock(rwlock1)

    def test_lock_fail_timeout(self):
        """test lock fail with timeout"""
        # Simulate other process
        client1 = RwlockClient(pid=str(os.getpid() - 1))
        client2 = RwlockClient()
        rwlock1 = client1.lock('N1', Rwlock.READ)
        t1 = time.monotonic()
        rwlock2 = client2.lock('N1', Rwlock.WRITE, timeout=0.2)
        t2 = time.monotonic()
        self.assertTrue(t2 - t1 > 0.2)
        self.assertEqual(rwlock2.status, Rwlock.TIMEOUT)
        client1.unlock(rwlock1)


class TestRedisRwlock_gc(unittest.TestCase):

    def setUp(self):
        cleanUpRedisKeys()

    def tearDown(self):
        cleanUpRedisKeys()

    def test_gc(self):
        """
        test gc by lock then exit without unlock
        """
        # Client1: N-GC1 --- exit
        # Client2: -------------- gc --- N-GC1
        client1_command = '''\
from redisrwlock import Rwlock, RwlockClient
client = RwlockClient()
client.lock('N-GC1', Rwlock.READ)
'''
        client1 = subprocess.Popen(['python3', '-c', client1_command])
        client1.wait()
        message = 'gc: 1 lock(s), 0 wait(s), 1 owner(s)'
        self.assertTrue(runGcExpect(message))
        client2 = RwlockClient()
        rwlock2 = client2.lock('N-GC1', Rwlock.WRITE)
        self.assertEqual(rwlock2.status, Rwlock.OK)
        client2.unlock(rwlock2)

    def test_gc_wait(self):
        """test gc when there is stale wait set"""
        # Client1: N-GC1 ------------ terminate client2 --- gc
        # Client2:       N-GC1 - wait
        client1 = RwlockClient()
        rwlock1_1 = client1.lock('N-GC1', Rwlock.READ)
        client2_command = '''\
from redisrwlock import Rwlock, RwlockClient
import sys
client = RwlockClient()
rwlock2_1 = client.lock('N-GC1', Rwlock.WRITE, timeout=Rwlock.FOREVER)
'''
        client2 = subprocess.Popen(['python3', '-c', client2_command])
        time.sleep(0.5)  # enough time for client2 to start wait
        client2.terminate()
        client2.wait()
        message = 'gc: 0 lock(s), 1 wait(s), 0 owner(s)'
        self.assertTrue(runGcExpect(message))
        client1.unlock(rwlock1_1)


class TestRedisRwlock_deadlock(unittest.TestCase):

    def setUp(self):
        cleanUpRedisKeys()

    def tearDown(self):
        cleanUpRedisKeys()
        pass

    def test_deadlock(self):
        """test deadlock detection"""
        # Client1: N-DL1 --------------- N-DL2
        # Client2:       N-DL2 --- N-DL1 (victim)
        client1 = RwlockClient()
        rwlock1_1 = client1.lock('N-DL1', Rwlock.WRITE, timeout=Rwlock.FOREVER)
        client2_command = '''\
from redisrwlock import Rwlock, RwlockClient
import sys
client = RwlockClient()
rwlock2_2 = client.lock('N-DL2', Rwlock.WRITE, timeout=Rwlock.FOREVER)
rwlock2_1 = client.lock('N-DL1', Rwlock.WRITE, timeout=Rwlock.FOREVER)
status = 0 if rwlock2_1.status == Rwlock.DEADLOCK else 1
client.unlock(rwlock2_2) # unblock client1 from lock
sys.exit(status)
'''
        client2 = subprocess.Popen(['python3', '-c', client2_command])
        time.sleep(1)
        t1 = time.monotonic()
        rwlock1_2 = client1.lock('N-DL2', Rwlock.READ, timeout=2)
        t2 = time.monotonic()
        self.assertTrue(t2 - t1 < 2)
        self.assertEqual(rwlock1_2.status, Rwlock.OK)
        client1.unlock(rwlock1_1)
        client1.unlock(rwlock1_2)
        self.assertEqual(client2.wait(), 0)

    def test_deadlock_with_many_locks(self):
        """test deadlock when victim has many granted locks.

        cover [lock can be deleted if DEADLOCK victim unlocked]
        in _oldest_lock_access_time()"""
        # Client1: N-DL1 ------------------- N-DL2
        # Client2:       ... N-DL2 --- N-DL1 (victim)
        # In '...', have many locks unrelated to deadlock
        client1 = RwlockClient()
        rwlock1_1 = client1.lock('N-DL1', Rwlock.WRITE, timeout=Rwlock.FOREVER)
        client2_command = '''\
from redisrwlock import Rwlock, RwlockClient
import sys
client = RwlockClient()
# locks many unrelated successfully
rwlock2_many = list()
for i in range(0, 1000):
    rwlock2_many.append(client.lock('N-DL2-#' + str(i), Rwlock.READ))
rwlock2_2 = client.lock('N-DL2', Rwlock.WRITE, timeout=Rwlock.FOREVER)
rwlock2_1 = client.lock('N-DL1', Rwlock.WRITE, timeout=Rwlock.FOREVER)
status = 0 if rwlock2_1.status == Rwlock.DEADLOCK else 1
client.unlock(rwlock2_2)  # unblock client1 from lock
for i in range(0, 1000):
    client.unlock(rwlock2_many[999 - i])
sys.exit(status)
'''
        client2 = subprocess.Popen(['python3', '-c', client2_command])
        time.sleep(2)
        t1 = time.monotonic()
        rwlock1_2 = client1.lock('N-DL2', Rwlock.READ, timeout=2,
                                 retry_interval=0)
        t2 = time.monotonic()
        self.assertTrue(t2 - t1 < 2)
        self.assertEqual(rwlock1_2.status, Rwlock.OK)
        client1.unlock(rwlock1_1)
        client1.unlock(rwlock1_2)
        self.assertEqual(client2.wait(), 0)
