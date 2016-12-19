from redisrwlock import Rwlock, RwlockClient
import unittest
import os
import subprocess
import time


class TestRedisRwlock(unittest.TestCase):

    def setUp(self):
        RwlockClient().clear_all()

    def tearDown(self):
        RwlockClient().clear_all()

    def test_lock(self):
        """
        test simple lock
        """
        client = RwlockClient()
        # read lock
        rwlock1 = client.lock('N1', Rwlock.READ)
        self.assertEqual(rwlock1.valid, True)
        self.assertEqual(rwlock1.name, 'N1')
        self.assertEqual(rwlock1.mode, Rwlock.READ)
        self.assertEqual(rwlock1.pid, str(os.getpid()))
        client.unlock(rwlock1)
        # write lock
        rwlock2 = client.lock('N2', Rwlock.WRITE)
        self.assertEqual(rwlock2.valid, True)
        self.assertEqual(rwlock2.name, 'N2')
        self.assertEqual(rwlock2.mode, Rwlock.WRITE)
        self.assertEqual(rwlock2.pid, str(os.getpid()))
        client.unlock(rwlock2)

    def test_unlock(self):
        """
        test normal unlock after lock
        """
        client = RwlockClient()
        rwlock1 = client.lock('N1', Rwlock.READ)
        self.assertEqual(client.unlock(rwlock1), True)

    def test_unlock_excessive(self):
        """
        test call unlock more than lock
        """
        client = RwlockClient()
        # read lock
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
        self.assertEqual(rwlock2.valid, True)
        self.assertEqual(rwlock2.name, 'N1')
        self.assertEqual(rwlock2.mode, Rwlock.READ)
        self.assertEqual(rwlock2.pid, rwlock1.pid)
        client.unlock(rwlock2)
        client.unlock(rwlock1)
        # R then W
        rwlock1 = client.lock('N2', Rwlock.READ)
        rwlock2 = client.lock('N2', Rwlock.WRITE)
        self.assertEqual(rwlock2.valid, True)
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
        self.assertEqual(rwlock2.valid, False)
        client1.unlock(rwlock1)

    def test_lock_fail_timeout(self):
        """test lock timeout non-zero"""
        # Simulate other process
        client1 = RwlockClient(pid=str(os.getpid() - 1))
        client2 = RwlockClient()
        rwlock1 = client1.lock('N1', Rwlock.READ)
        t1 = time.monotonic()
        rwlock2 = client2.lock('N1', Rwlock.WRITE, timeout=0.2)
        t2 = time.monotonic()
        self.assertTrue(t2 - t1 > 0.2)
        self.assertEqual(rwlock2.valid, False)
        client1.unlock(rwlock1)


class TestRedisRwlock_gc(unittest.TestCase):

    def setUp(self):
        self.gc = subprocess.Popen(['python3', 'redisrwlock.py'])

    def tearDown(self):
        self.gc.terminate()

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
        self.assertEqual(rwlock2.valid, True)
        client2.unlock(rwlock2)
