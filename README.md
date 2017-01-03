# redisrwlock

Distributed read-write lock for python using redis as server

## Features

* Read-write lock (can have multiple readers or one exclusive writer)
* Stale locks collected (run as separate process, $ python3 -m redisrwlock)
* Deadlock detection

Note: Deadlock detection and garbage/staleness collection is done in
client side, which can cause excessive I/O with redis server.  Tune
with `retry_interval` and `redis-sentinel`ed gc command for your task.

## Dependencies

* python 3.5.2
* redis-py 2.10.5
* redis 3.2.6
* [test] Coverage.py 4.2

## Usages

### Install

...

### Try lock with timeout=0

With timeout=0, RwlockClinet.lock acts as so called try_lock.

``` python
from redisrwlock import Rwlock, RwlockClient
import redis

client = RwlockClient()
rwlock = client.lock('N1', Rwlock.READ, timeout=0)
if rwlock.status == Rwlock.OK:
    # Processings of resource named 'N1' with READ lock
    # ...
    client.unlock(rwlock)
elif rwlock.status == Rwlock.FAIL:
    # Retry locking or quit
```

### Waiting until lock success or deadlock

With timout > 0, RwlockClient.lock waits until lock successfully or
deadlock detected and caller is chosen as victim.

``` python
from redisrwlock import Rwlock, RwlockClient

client = RwlockClient()
rwlock = client.lock('N1', Rwlock.READ, timeout=Rwlock.FOREVER)
if rwlock.status == Rwlock.OK:
    # Processings of resource named 'N1' with READ lock
    # ...
    client.unlock(rwlock)
elif rwlock.status == Rwlock.DEADLOCK:
    # 1. unlock if holding any other locks
    # 2. Retry locking or quit
```

### Removing stale locks

When a client exits without unlock, redis keys for the client's locks
remain in server and block other clients from successful locking.
`redisrwlock` run in command line removes such garbage locks, waits
in server.

``` shell
python3 -m redisrwlock
```

You can repeat this gc periodically by specifying -r or --repeat option.

## Tests

### Unittest

``` shell
python3 -m unittest -q
```

### Coverage

``` shell
coverage erase
coverage run -a -m unittest -q
coverage html
```

Above simple coverage run will report lower coverage than expected
because the tests use subprocess. Codes run by subprocess are not
covered in report by default.

### Subprocess coverage

Need some preperation:

1. Edit `sitecustomize.py` (under python intallation's `site-packages` directory), add 2 lines

    ``` python
    import coverage
    coverage.process_startup()
    ```

2. Edit `.coveragerc` (default name of coverage.py's config file)

    ```
    [run]
    branch = True
    [html]
    directory = htmlcov

    ```

Then, run coverage with environment variable `COVERAGE_PROCESS_START`={path/to/coveragerc}

``` shell
coverage erase
COVERAGE_PROCESS_START=.coveragerc coverage run -a -m unittest -q
coverage html
```

## TODOs

* TODO: packaging
* TODO: high availability! redis sentinel or replication?
