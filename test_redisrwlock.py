from redisrwlock import Rwlock, RwlockClient
from test_redisrwlock_connection import runRedisServer, terminateRedisServer

import unittest
import os
import subprocess
import time


def setUpModule():
    global _server, _dumper
    _server, _dumper = runRedisServer()


def tearDownModule():
    global _server, _dumper
    terminateRedisServer(_server, _dumper)


class TestRedisRwlock(unittest.TestCase):

    def setUp(self):
        RwlockClient()._clear_all()

    def tearDown(self):
        RwlockClient()._clear_all()

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
        RwlockClient()._clear_all()
        self.gc = subprocess.Popen(['python3', 'redisrwlock.py'])

    def tearDown(self):
        self.gc.terminate()
        RwlockClient()._clear_all()

    def test_gc(self):
        """
        test gc by lock then exit without unlock
        """
        # Client1 lock then exit without unlock
        client1_command = '''\
from redisrwlock import Rwlock, RwlockClient
client = RwlockClient()
client.lock('N-GC1', Rwlock.READ)
'''
        client1 = subprocess.Popen(['python3', '-c', client1_command])
        client1.wait()
        # print("DEBUG client1 return: " + str(client1.returncode))
        # --
        # Now, client2 try lock fail without gc, pass with gc
        # need to specify timeout greater than gc interval (5 sec)
        client2 = RwlockClient()
        rwlock2 = client2.lock('N-GC1', Rwlock.WRITE, timeout=10)
        self.assertEqual(rwlock2.status, Rwlock.OK)
        client2.unlock(rwlock2)


class TestRedisRwlock_deadlock(unittest.TestCase):

    def setup(self):
        RwlockClient()._clear_all()

    def tearDown(self):
        RwlockClient()._clear_all()

    def test_deadlock(self):
        """test deadlock detection"""
        # Client1: N-DL1 ----------------- sleep(1) --- N-DL2
        # Client2:        N-DL2 --- N-DL1
        client1 = RwlockClient()
        client1.lock('N-DL1', Rwlock.WRITE)
        client2_command = '''\
from redisrwlock import Rwlock, RwlockClient
client = RwlockClient()
client.lock('N-DL2', Rwlock.WRITE)
client.lock('N-DL1', Rwlock.WRITE)
# TEST should return after deadlock detected in client1
'''
        client2 = subprocess.Popen(['python3', '-c', client2_command])
        time.sleep(1)
        # This should result in deadlock before timeout
        t1 = time.monotonic()
        rwlock1_2 = client1.lock('N-DL2', Rwlock.READ, timeout=1)
        t2 = time.monotonic()
        self.assertEqual(rwlock1_2.status, Rwlock.DEADLOCK)
        # print("DEBUG t2 - t1 =" + str(t2 - t1))
        self.assertTrue(t2 - t1 < 1)
