# Coverage test of __main__.py, no tight checks on output messages
from test_redisrwlock_connection import runRedisServer, terminateRedisServer

import unittest
import os
import signal
import subprocess


# Run command return exit status and output messages.
# When wait is False, read at most limit lines and retrn without wait
def runCmdOutput(args, wait=True, limit=0):
    cmd_args = ['python3', '-m', 'redisrwlock'] + args
    cmd = subprocess.Popen(cmd_args,
                           stdout=subprocess.PIPE,
                           universal_newlines=True)
    output = list()
    count = 0
    for line in cmd.stdout:
        output.append(line)
        if not wait:
            count += 1
            if count >= limit:
                break
    if wait:
        cmd.wait()
        cmd.stdout.close()
    return cmd, output


def setUpModule():
    global _server, _dumper
    _server, _dumper = runRedisServer(port=7788)


def tearDownModule():
    global _server, _dumper
    terminateRedisServer(_server, _dumper)


class TestRedisRwlock_cmdline(unittest.TestCase):

    def test_option_unrecognized(self):
        """test usage error for unrecognized option"""
        cmd, output = runCmdOutput(['--unrecognized'])
        self.assertEqual(cmd.returncode, os.EX_USAGE)

    def test_option_unhandled(self):
        """test not handled option with hidden test option"""
        cmd, output = runCmdOutput(['--__unhandled__'])
        self.assertEqual(cmd.returncode, os.EX_USAGE)

    def test_option_help(self):
        """test --help option"""
        cmd, output = runCmdOutput(['--help'])
        self.assertEqual(cmd.returncode, os.EX_OK)

    def test_option_version(self):
        """test --version option"""
        cmd, output = runCmdOutput(['--version'])
        self.assertEqual(cmd.returncode, os.EX_OK)

    def test_option_repeat_interval(self):
        """test --retry and --interval options"""
        # run with --retry, see 2 lines, then kill -INT
        cmd, output = runCmdOutput(['-p', '7788', '-r'],
                                   wait=False, limit=2)
        cmd.send_signal(signal.SIGINT)
        self.assertEqual(cmd.wait(), 1)
        cmd.stdout.close()
        # run with --retry, see 4 lines, then kill -INT
        cmd, output = runCmdOutput(['-p', '7788', '-r', '-i', '1'],
                                   wait=False, limit=4)
        cmd.send_signal(signal.SIGINT)
        self.assertEqual(cmd.wait(), 1)
        cmd.stdout.close()
        # invalid --interval option argument (int > 0)
        cmd, output = runCmdOutput(['-p', '7788', '-i', '0'])
        self.assertEqual(cmd.returncode, os.EX_USAGE)
        # --interval option argument ignored if no --retry
        cmd, output = runCmdOutput(['-p', '7788', '-i', '1000'])
        self.assertEqual(cmd.returncode, os.EX_OK)

    def test_option_server_port(self):
        """test --server and --port options"""
        # empty redis-server host name
        cmd, output = runCmdOutput(['-s', '', '-p', '7788'])
        self.assertEqual(cmd.returncode, os.EX_USAGE)
        # port number out of range
        cmd, output = runCmdOutput(['-s', 'localhost', '-p', '99999'])
        self.assertEqual(cmd.returncode, os.EX_USAGE)

    def test_logging_config(self):
        """test logging config from file or default"""
        topdir = os.path.dirname(os.path.dirname(__file__))
        # logging config from default
        os.system('rm %s/logging.conf' % topdir)
        cmd, output = runCmdOutput(['-p', '7788'])
        self.assertEqual(cmd.returncode, os.EX_OK)
        # logging config from file
        os.system('cp %s/logging.conf.sample %s/logging.conf' %
                  (topdir, topdir))
        cmd, output = runCmdOutput(['-p', '7788'])
        self.assertEqual(cmd.returncode, os.EX_OK)
