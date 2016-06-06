import time

import game
import util


_STALE_THRESHOLD = 600  # 10 minutes.


class GameListing(object):
  """Thread-safe game listing."""

  def __init__(self):
    self.lock = util.RWLock()
    self.ongoing_games = {}

  def New(self, creator, max_players, circuit_name=None):
    with self.lock(util.READ_LOCKED):
      new_game = game.Game(creator, max_players, circuit_name)
      while new_game.id in self.ongoing_games:
        new_game = game.Game(max_players, circuit_name)
      self.lock.promote()  # Now write locked.
      self.ongoing_games[new_game.id] = new_game
    return new_game

  def JSONData(self):
    with self.lock(util.READ_LOCKED):
      return [v.JSONData() for v in self.ongoing_games.itervalues() if v.IsOpen()]

  def Get(self, game_id):
    with self.lock(util.READ_LOCKED):
      return self.ongoing_games[game_id]

  def AddPlayer(self, game_id, user):
    game_instance = self.Get(game_id)
    game_instance.AddPlayer(user)

  def Refresh(self, game_id):
    self.Get(game_id).Refresh()

  def GarbageCollect(self):
    # TODO: Make this more efficient with a hashed linked list.
    current_time = int(time.time())
    remove = []
    with self.lock(util.READ_LOCKED):
      for game_id, game_instance in self.ongoing_games.iteritems():
        if current_time - game_instance.refresh_date > _STALE_THRESHOLD:
          remove.append(game_id)
      if remove:
        self.lock.promote()  # Write locked.
        for game_id in remove:
          game_instance = self.ongoing_games.pop(game_id)

  def Stop(self):
    with self.lock(util.READ_LOCKED):
      for game_instance in self.ongoing_games.itervalues():
        game_instance.Stop()
