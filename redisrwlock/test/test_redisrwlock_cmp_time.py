from redisrwlock import _cmp_time

import unittest


class TestRedisRwlock(unittest.TestCase):

    def test_cmp_time(self):
        # seconds part rules
        self.assertTrue(_cmp_time('30.0', '4.0') > 0)
        self.assertTrue(_cmp_time('30.1', '4.2') > 0)
        self.assertTrue(_cmp_time('30.2', '4.1') > 0)
        self.assertTrue(_cmp_time('3.0', '4.0') < 0)
        self.assertTrue(_cmp_time('3.1', '4.2') < 0)
        self.assertTrue(_cmp_time('3.2', '4.1') < 0)
        # when seconds part equal, micro-seconds part are significant
        self.assertTrue(_cmp_time('0.30', '0.4') > 0)
        self.assertTrue(_cmp_time('0.3', '0.3') == 0)
        self.assertTrue(_cmp_time('0.3', '0.4') < 0)
