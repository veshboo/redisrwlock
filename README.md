# redisrwlock

Distributed read-write lock for python using redis as server

## Features

* Read-write lock (can have multiple readers or one exclusive writer)
* Stale locks collected (run as separate process, $ python3 redisrwlock.py)
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

* Please consult `test_redisrwlock.py` and `test_redisrwlock_connection.py`

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

* TODO: high availability! redis sentinel or replication?
