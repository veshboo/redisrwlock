# redisrwlock

Global (multi-node) read-write lock for python using redis as server

## dependencies

* python 3.5.2
* redis-py 2.10.5
* redis 3.2.6

## features

* Read-write lock (can have multiple readers or one exclusive writer)
* Stale locks collected (run as separate process, $ python3 redisrwlock.py)
* Deadlock detection

Note: Deadlock detection is done in client side, which can cause excessive I/O
with Redis server. Tune with retry_interval for your task.

## usages

* Please consult test_redisrwlock.py
* Before running test, redis-server should be running first

## TODOs

* High availability
