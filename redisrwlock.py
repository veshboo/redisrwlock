from __future__ import print_function

import redis

import logging
import logging.config
import os
import re
import time

logging.config.fileConfig('logging.conf')

# (1) Primary data structure for lock, owner, grant
#
# SET:    rsrc name -> set of lock grants
# STRING: lock name -> ref count
# rsrc    ::= rsrc:{name of resource}
# grant   ::= {mode}:{owner}
# lock    ::= lock:{name of resource}:{mode}:{owner}
# owner   ::= {node}/{pid}
#
# (2) Addtional data structure for deadlock detect wait-for graph
#
# SET:    waitor -> set of waitee
# waitor  ::= wait:{owner}
# waitee  ::= {owner}

_LOCK_SCRIPT = """\
local rsrc = KEYS[1]
local lock = KEYS[2]
local mode = string.match(lock, 'lock:.+:([RW]):.+')
local owner = string.match(lock, 'lock:.+:[RW]:(.+)')
local grants = redis.call('smembers', rsrc)
for i, grant in ipairs(grants) do
    local grant_mode = string.match(grant, '([RW]):.+')
    local grant_owner = string.match(grant, '[RW]:(.+)')
    if grant_owner ~= owner then
        if not (grant_mode == 'R' and mode == 'R') then
            return 'false'
        end
    end
end
redis.call('sadd', rsrc, mode..':'..owner)
redis.call('incr', lock)
return 'true'
"""

_UNLOCK_SCRIPT = """
local rsrc = KEYS[1]
local lock = KEYS[2]
local mode = string.match(lock, 'lock:.+:([RW]):.+')
local owner = string.match(lock, 'lock:.+:[RW]:(.+)')
local retval = redis.call('get', lock)
if retval == false then
    return 'false'
else
    if tonumber(retval) == 1 then
        redis.call('del', lock)
        redis.call('srem', rsrc, mode..':'..owner)
        if redis.call('scard', rsrc) == 0 then
            redis.call('del', rsrc)
        end
    else
        redis.call('decr', lock)
    end
end
return 'true'
"""

_REMOVE_GRANT_SCRIPT = """
local rsrc = KEYS[1]
local grant = ARGV[1]
redis.call('srem', rsrc, grant)
if redis.call('scard', rsrc) == 0 then
    redis.call('del', rsrc)
end
"""


# lock result used as token
class Rwlock:
    """
    Constants for Rwlock

    lock modes: READ, WRITE

    special timeout: FOREVER

    status: OK, FAIL, TIMEOUT, DEADLOCK,
    and None if not returned from lock method
    """

    # lock modes
    READ = 'R'
    WRITE = 'W'

    # timeout
    FOREVER = -1

    # status
    OK = 0
    FAIL = 1
    TIMEOUT = 2
    DEADLOCK = 3

    def __init__(self, name, mode, node, pid):
        self.name = name
        self.mode = mode
        self.node = node
        self.pid = pid
        self.status = None

    def get_rsrc(self):
        return 'rsrc:' + self.name

    def get_lock(self):
        return self.__str__()

    def __str__(self):
        return 'lock:' + self.name + ':' + self.mode + ':' + self.node + '/' + self.pid


class RwlockClient:

    def __init__(self,
                 redis=redis.StrictRedis(),
                 node='localhost', pid=str(os.getpid())):
        self.redis = redis
        self.node = node
        self.pid = pid
        self.redis.client_setname('redisrwlock:' + self.node + '/' + self.pid)

    def get_owner(self):
        return self.node + '/' + self.pid

    def lock(self, name, mode, timeout=0, retry_interval=0.1):
        """Locks on a named resource with mode in timeout.

        Specify timeout 0 (default) for no-wait, no-retry and
        timeout FOREVER waits until lock success or deadlock.

        When requested lock is not available, this method sleep
        given retry_interval seconds and retry until lock success,
        deadlock or timeout.

        returns rwlock, check status field to know lock obtained or failed
        """
        t1 = t2 = time.monotonic()
        rwlock = Rwlock(name, mode, self.node, self.pid)
        while timeout == Rwlock.FOREVER or t2 - t1 <= timeout:
            retval = self.redis.eval(
                _LOCK_SCRIPT, 2, rwlock.get_rsrc(), rwlock.get_lock())
            lock_ok = True if retval == b'true' else False
            if lock_ok:
                rwlock.status = Rwlock.OK
                break
            elif timeout == 0:
                rwlock.status = Rwlock.FAIL
                break
            elif self._deadlock(name, mode):
                rwlock.status = Rwlock.DEADLOCK
                break
            time.sleep(retry_interval)
            t2 = time.monotonic()
        else:
            rwlock.status = Rwlock.TIMEOUT
        self.redis.delete('wait:' + self.get_owner())
        return rwlock

    def unlock(self, rwlock):
        """Unlocks rwlock previously acquired with lock method

        returns true for successfull unlock
        false if there is no such lock to unlock
        """
        retval = self.redis.eval(
            _UNLOCK_SCRIPT, 2, rwlock.get_rsrc(), rwlock.get_lock())
        return retval == b'true'

    # TODO: Avoid full scan of lock list
    # by introducing owner:oname -> { set of resources names }
    # with this additional info, I can;
    # (1) find out stale owners
    # (2) then unlock locks of each stale owner
    def gc(self):
        """Removes stale locks and waits created by crashed/exit
        clients without unlocking or proper cleanup.

        Used by garbage collecting daemon or monitor
        """
        # Get lock and wait list before client list
        # Otherwise, we may mistakenly remove locks or waits
        # made by last clients not included in the client list
        lock_list = self.redis.keys('lock:*:[RW]:*')
        wait_list = self.redis.keys('wait:*')
        active_set = set()
        for client in self.redis.client_list():
            m = re.match(r'redisrwlock:(.+)', client['name'])
            if m:
                active_set.add(m.group(1))
        count = 0
        # Gc stale lock and grant
        for lock in lock_list:
            m = re.match(r'lock:(.+):([RW]):(.+)', lock.decode())
            assert m is not None
            name, mode, owner = m.group(1, 2, 3)
            if owner not in active_set:
                self.redis.delete(lock)
                # 'SREM' and 'DEL' should be done in atomic
                self.redis.eval(
                    _REMOVE_GRANT_SCRIPT, 1, 'rsrc:'+name, mode+':'+owner)
                count += 1
                logging.debug('gc: ' + lock.decode())
        if count > 0:
            logging.debug('gc: ' + str(count) + ' lock(s)')
        count = 0
        # Gc stale waitor and waitee
        for wait in wait_list:
            waitor = re.match(r'wait:(.+)', wait.decode()).group(1)
            if waitor not in active_set:
                # XXX 'SREM' from other waitors with this waitor as member
                # This seems not required, because active waitors rebuild
                # their wait sets when they retry locking.
                # --
                # self.redis.eval(_REMOVE_WAITEE_SCRIPT, 0, waitor)
                self.redis.delete(wait)
                count += 1
                logging.debug('gc: ' + wait.decode())
        if count > 0:
            logging.debug('gc: ' + str(count) + ' wait(s)')

    def _deadlock(self, name, mode):
        self._waitset(name, mode)
        myself, visited, path = self.get_owner(), set(), list()
        if self._cyclic(myself, visited, path):
            return self._victim(path)
        return False

    # This could be done in _LOCK_SCRIPT, but here to satisfy redis
    # EVAL KEYS semantic
    def _waitset(self, name, mode):
        """Make sure wait set is up to date before deadlock detection"""
        myself = self.get_owner()
        grants = self.redis.smembers('rsrc:' + name)
        self.redis.sadd('wait:' + myself, '__dummy__')
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            waitees = list()
        for grant in grants:
            m = re.match(r'([RW]):(.+)', grant.decode())
            grant_mode, grant_owner = m.group(1, 2)
            if grant_owner != myself:
                if not (grant_mode == Rwlock.READ and mode == Rwlock.READ):
                    retval = self.redis.scard('wait:' + grant_owner)
                    if retval:
                        self.redis.sadd('wait:' + myself, grant_owner)
                        if logging.getLogger().isEnabledFor(logging.DEBUG):
                            waitees.append(grant_owner)
                    else:
                        self.redis.srem('wait:' + myself, grant_owner)
        if logging.getLogger().isEnabledFor(logging.DEBUG) and waitees:
            logging.debug('waitset: %s waits {%s}', myself, ', '.join(waitees))

    # Deadlock detect - cycle detect in wait-for graph (DAG)
    # DFS checking rediscovering of vertex in path
    def _cyclic(self, current, visited, path):
        if current in path:
            logging.debug("_cyclic: [%s]", '->'.join(path))
            return True
        adj_set = self.redis.smembers('wait:' + current)
        for adj in adj_set:
            adj = adj.decode()
            if adj not in visited:
                path.append(current)
                if self._cyclic(adj, visited, path):
                    return True
                path.pop()
        visited.add(current)
        return False

    # FIXME: Introduce time when lock first granted to determine victim
    # Current implementation just determine with process id.
    #
    # Among the waitors in cycle, one who lives long with granted lock
    # will survive.
    # (1) oldest lock granted for each waitor
    # (2) victim waitor with youngest lock granted obtained from (1)
    def _victim(self, path):
        myself = self.get_owner()
        for waitor in path:
            if waitor < myself:
                logging.debug('_victim: %s, not victim. retry ...', myself)
                return False
        logging.debug('_victim: %s, the victim. DEADLOCK.', myself)
        return True

    # For test aid, not public
    def _clear_all(self):
        count = 0
        for lock in self.redis.keys('lock:*:[RW]:*'):
            logging.debug('_clear_all: ' + lock.decode())
            count += self.redis.delete(lock.decode())
        for rsrc in self.redis.keys('rsrc:*'):
            logging.debug('_clear_all: ' + rsrc.decode())
            count += self.redis.delete(rsrc.decode())
        for wait in self.redis.keys('wait:*'):
            logging.debug('_clear_all: ' + wait.decode())
            count += self.redis.delete(wait.decode())
        return True if count > 0 else False


# Gc periodically
if __name__ == '__main__':

    while True:
        _client = RwlockClient()
        _client.gc()
        logging.debug('redisrwlock gc')
        time.sleep(5)

# TODO: high availability! research if redis-sentinel can help
