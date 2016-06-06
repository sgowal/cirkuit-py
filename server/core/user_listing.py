import time

import user
import util


_USERNAME_MAX_LENGTH = 15
_STALE_THRESHOLD = 600  # 10 minutes.


class Error(Exception):
  pass


class UsernameExistsError(Error):
  pass


class UserListing(object):
  """Thread-safe user listing."""

  def __init__(self):
    self.lock = util.RWLock()
    self.users = {}
    self.usernames = set()

  def New(self, username):
    if not username or len(username) > _USERNAME_MAX_LENGTH:
      raise UsernameExistsError('Cannot have empty username.')
    with self.lock(util.READ_LOCKED):
      if username in self.usernames:
        raise UsernameExistsError()
      new_user = user.User(username)
      while new_user.id in self.users:
        new_user = user.User(username)
      self.lock.promote()  # Write locked.
      self.users[new_user.id] = new_user
      self.usernames.add(username)
    return new_user

  def Get(self, user_id):
    with self.lock(util.READ_LOCKED):
      return self.users[user_id]

  def Remove(self, user_id):
    with self.lock(util.WRITE_LOCKED):
      user_instance = self.users.pop(user_id)
      self.usernames.remove(user_instance.username)

  def Refresh(self, user_id):
    self.Get(user_id).Refresh()

  def GarbageCollect(self):
    # TODO: Make this more efficient with a hashed linked list.
    current_time = int(time.time())
    remove = []
    with self.lock(util.READ_LOCKED):
      for user_id, user_instance in self.users.iteritems():
        if current_time - user_instance.refresh_date > _STALE_THRESHOLD:
          remove.append(user_id)
      if remove:
        self.lock.promote()  # Write locked.
        for user_id in remove:
          user_instance = self.users.pop(user_id)
          self.usernames.remove(user_instance.username)
