import threading


READ_LOCKED = 0
WRITE_LOCKED = 1


class _Locking(object):
  def __init__(self, lock, locking_mechanism):
    self.lock = lock
    self.locking_mechanism = locking_mechanism

  def __enter__(self):
    if self.locking_mechanism == READ_LOCKED:
      self.lock.acquire_read()
    else:
      self.lock.acquire_write()
    return self.lock

  def __exit__(self, unused_type, unused_value, unused_traceback):
    self.lock.release()


class RWLock(object):

  def __init__(self):
    self.rwlock = 0
    self.writers_waiting = 0
    self.monitor = threading.Lock()
    self.readers_ok = threading.Condition(self.monitor)
    self.writers_ok = threading.Condition(self.monitor)

  # Some syntatic sugar for lock using "with". Allows to do:
  # with my_lock(READ_LOCKED):  (or)  with my_lock(WRITE_LOCKED):
  #   ...                               ...
  def __call__(self, locking_mechanism=READ_LOCKED):
    return _Locking(self, locking_mechanism)

  def acquire_read(self):
    self.monitor.acquire()
    while self.rwlock < 0 or self.writers_waiting:
      self.readers_ok.wait()
    self.rwlock += 1
    self.monitor.release()

  def acquire_write(self):
    self.monitor.acquire()
    while self.rwlock != 0:
      self.writers_waiting += 1
      self.writers_ok.wait()
      self.writers_waiting -= 1
    self.rwlock = -1
    self.monitor.release()

  def promote(self):
    self.monitor.acquire()
    self.rwlock -= 1
    while self.rwlock != 0:
      self.writers_waiting += 1
      self.writers_ok.wait()
      self.writers_waiting -= 1
    self.rwlock = -1
    self.monitor.release()

  def demote(self):
    self.monitor.acquire()
    self.rwlock = 1
    self.readers_ok.notifyAll()
    self.monitor.release()

  def release(self):
    self.monitor.acquire()
    if self.rwlock < 0:
      self.rwlock = 0
    else:
      self.rwlock -= 1
    wake_writers = self.writers_waiting and self.rwlock == 0
    wake_readers = self.writers_waiting == 0
    self.monitor.release()
    if wake_writers:
      self.writers_ok.acquire()
      self.writers_ok.notify()
      self.writers_ok.release()
    elif wake_readers:
      self.readers_ok.acquire()
      self.readers_ok.notifyAll()
      self.readers_ok.release()
