import redis

import logging
import logging.config
import os
import re
import time

logging.config.fileConfig('logging.conf')

# Primary data structure for lock, owner, grant
#
# SET:    rsrc name -> set of lock grants
# STRING: lock name -> ref count
# rsrc    ::= rsrc:{name of resource}
# grant   ::= {mode}:{owner}
# lock    ::= lock:{name of resource}:{mode}:{owner}
# owner   ::= {node}/{pid}

# Addtional data structure for deadlock detect wait-for graph
# SET:    waitor -> set of waitee
# waitor  ::= wait:{owner}
# waitee  ::= {owner}

_LOCK_SCRIPT = """\
local rsrc = KEYS[1]
local lock = KEYS[2]
local mode = string.match(lock, 'lock:.+:([RW]):.+')
local owner = string.match(lock, 'lock:.+:[RW]:(.+)')
local grants = redis.call('smembers', rsrc)
local any_wait = false
for i, grant in ipairs(grants) do
    local grant_mode = string.match(grant, '([RW]):.+')
    local grant_owner = string.match(grant, '[RW]:(.+)')
    if grant_owner ~= owner then
        if not (grant_mode == 'R' and mode == 'R') then
            any_wait = true
            redis.call('sadd', 'wait:'..owner, grant_owner)
        end
    end
end
if any_wait then
    return 'false'
else
    redis.call('sadd', rsrc, mode..':'..owner)
    redis.call('incr', lock)
    return 'true'
end
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

_CLEAR_ALL_SCRIPT = """
local locks = redis.call('keys', 'lock:*:[RW]:*')
for i, lock in ipairs(locks) do
    redis.call('del', lock)
end
local rsrcs = redis.call('keys', 'rsrc:*')
for i, rsrc in ipairs(rsrcs) do
    redis.call('del', rsrc)
end
local waits = redis.call('keys', 'wait:*')
for i, wait in ipairs(waits) do
    redis.call('del', wait)
end
"""


# lock result used as token
class Rwlock:
    READ = 'R'
    WRITE = 'W'
    FOREVER = -1

    def __init__(self, name, mode, node, pid):
        self.name = name
        self.mode = mode
        self.node = node
        self.pid = pid
        self.valid = False

    def get_rsrc(self):
        return 'rsrc:' + self.name

    def get_lock(self):
        return self.__str__()

    def __str__(self):
        return 'lock:' + self.name + ':' + self.mode + ':' + self.node + '/' + self.pid


class RwlockClient:

    def __init__(self, node='localhost', pid=str(os.getpid())):
        self.redis = redis.StrictRedis()
        self.node = node
        self.pid = pid
        self.redis.client_setname('redisrwlock:' + self.node + '/' + self.pid)

    def lock(self, name, mode, timeout=0, retry_interval=0.1):
        """Locks on a named resource with mode in timeout.

        Specify timeout 0 (default) for no-wait, no-retry and
        timeout FOREVER waits until lock success or deadlock.
        -- Although deadlock detection is not implemented yet

        When requested lock is not available, this method sleep
        given retry_interval seconds and retry until lock success or timeout

        returns rwlock, check valid field to know lock obtained or failed
        """
        t1 = t2 = time.monotonic()
        rwlock = Rwlock(name, mode, self.node, self.pid)
        while timeout == Rwlock.FOREVER or t2 - t1 <= timeout:
            retval = self.redis.eval(
                _LOCK_SCRIPT, 2, rwlock.get_rsrc(), rwlock.get_lock())
            rwlock.valid = retval == b'true'
            if rwlock.valid:
                return rwlock
            time.sleep(retry_interval)
            t2 = time.monotonic()
        assert not rwlock.valid
        return rwlock

    def unlock(self, rwlock):
        """Unlocks rwlock previously acquired with lock method

        returns true for successfull unlock
        false if there is no such lock to unlock
        """
        retval = self.redis.eval(
            _UNLOCK_SCRIPT, 2, rwlock.get_rsrc(), rwlock.get_lock())
        return retval == b'true'

    # FIXME: Avoid full scan of lock list
    # by introducing owner:oname -> { set of resources names }
    # with this additional info, I can;
    # (1) find out stale owners
    # (2) then unlock locks of each stale owner
    def gc(self):
        """Removes stale locks created by crashed/exit
        clients without unlocking.

        Used by garbage collecting daemon or monitor
        """
        # Get lock list before client list
        # Otherwise, we may mistakenly remove locks made
        # by last clients not included in the client list
        lock_list = self.redis.keys('lock:*:[RW]:*')
        active_set = set()
        for client in self.redis.client_list():
            m = re.match(r'redisrwlock:(.+)', client['name'])
            if m:
                active_set.add(m.group(1))
        count = 0
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
            logging.info('gc: ' + str(count) + ' lock(s)')

    # For test aid, not public
    def _clear_all(self):
        self.redis.eval(_CLEAR_ALL_SCRIPT, 0)


# Gc periodically
if __name__ == '__main__':

    while True:
        _client = RwlockClient()
        _client.gc()
        logging.debug('redisrwlock gc')
        time.sleep(5)


# TODO: deadlock detection
# TODO: high availability! research if redis-sentinel can help
