import random
import string
import time

import user
import engine
import util

# Provides 8^(26*2) possible ids.
_ID_LENGTH = 8


class Error(Exception):
  pass


class GameFullError(Error):
  pass


class NotCreatorError(Error):
  pass


class NotStartedError(Error):
  pass


class Game(object):

  def __init__(self, creator, max_players, circuit_name=None):
    self.players_lock = util.RWLock()
    self.id = ''.join(random.choice(string.ascii_letters) for _ in xrange(_ID_LENGTH))
    self.creation_date = int(time.time())
    self.refresh_date = int(time.time())
    self.max_players = max_players
    self.players = []
    self.creator = creator
    self.race = engine.Race(circuit_name)
    self.user_dict = None
    self.race_started = False
    self.race_lock = util.RWLock()
    self.AddPlayer(creator)

  def Refresh(self):
    self.refresh_date = int(time.time())

  def JSONData(self):
    with self.players_lock(util.READ_LOCKED):
      return {
          'id': self.id, 'creation': self.creation_date,
          'num_players': len(self.players),
          'max_players': self.max_players,
          'players': [p.username for p in self.players]
      }

  def IsOpen(self):
    with self.race_lock(util.READ_LOCKED):
      return not self.race_started

  def AddPlayer(self, new_player):
    added = False
    with self.players_lock(util.WRITE_LOCKED):
      if self.IsOpen():  # We are guaranteed that usernames are unique.
        self.players.append(new_player)
        added = True
        if len(self.players) >= self.max_players:
          self.StartRace()
    if not added:
      raise GameFullError('Game already has %d players.', self.max_players)

  def RemovePlayer(self, authentication_id):
    # Game started.
    with self.race_lock(util.READ_LOCKED):
      if self.user_dict:
        self.user_dict[authentication_id].Stop(forced=True)
    # Remove from players list.
    with self.players_lock(util.WRITE_LOCKED):
      self.players.remove([p for p in self.players if p.id == authentication_id][0])

  def FillWithComputerPlayers(self, authentication_id, computer_ai):
    if authentication_id != self.creator.id:
      raise NotCreatorError('%s is not the creator of this game.' % authentication_id)
    if self.players_lock(util.WRITE_LOCKED):
      if self.IsOpen():  # Make sure that we don't start the race twice.
        while len(self.players) < self.max_players:
          new_user = user.User()
          if new_user.username not in (p.username for p in self.players):
            self.players.append(new_user)
        self.StartRace(computer_ai=computer_ai)

  def StartRace(self, computer_ai=None):
    # Start race with human and computer players.
    with self.race_lock(util.WRITE_LOCKED):
      users = [(p, engine.CreatePlayer(computer_ai if computer_ai else 'FixedDepthPlayer') if p.is_computer else engine.HumanPlayer()) for p in self.players]
      self.player_name_dict = dict((id(v), k.username) for k, v in users)
      self.user_dict = dict((k.id, v) for k, v in users if not k.is_computer)
      self.race_players = [v for k, v in users]
      self.race.Start(self.race_players)
      self.race_started = True

  def Stop(self):
    # Stop race if already started.
    with self.race_lock(util.WRITE_LOCKED):
      if self.race_started:
        self.race.Stop()

  def Play(self, move_index, authentication_id):
    # Try to play. If it's not the player's turn an exception is raised.
    # Raising a key error is also ok.
    with self.race_lock(util.READ_LOCKED):
      if self.race_started:
        self.user_dict[authentication_id].SetNextMove(move_index)

  def CircuitJSONData(self):
    return self.race.GetCircuit().JSONData()

  def RaceJSONData(self, authentication_id):
    # It is ok to raise a KeyError here.
    with self.race_lock(util.READ_LOCKED):
      if self.race_started:
        player_id = id(self.user_dict[authentication_id])
        game_data = self.race.GetSnapshot()
        playing_player = game_data['playing']
        return {
            'playing_now': self.player_name_dict[id(playing_player)] if playing_player else None,
            'moves': [{'x': m.xy[0], 'y': m.xy[1], 'status': m.status} for m in game_data['moves']] if playing_player else [],
            'is_turn': id(playing_player) == player_id if playing_player else False,
            'positions': dict((self.player_name_dict[id(p)], t) for p, t in zip(self.race_players, game_data['trajectories'])),
            'rounds': dict((self.player_name_dict[id(p)], s.round if s else 0) for p, s in zip(self.race_players, game_data['states'])),
            'laps': dict((self.player_name_dict[id(p)], s.lap if s else 0) for p, s in zip(self.race_players, game_data['states'])),
            'status': dict((self.player_name_dict[id(p)], _PlayerStatus(p, s)) for p, s in zip(self.race_players, game_data['states'])),
            'distance_left': dict((self.player_name_dict[id(p)], s.distance_left if s else -1.) for p, s in zip(self.race_players, game_data['states'])),
        }
      else:
        raise NotStartedError('Game not started yet.')


def _PlayerStatus(player, state):
  if player.IsStopped() and (state is None or state.status == engine.STATUS_RUNNING):
    return engine.STATUS_DISCONNECTED
  return state.status if state else engine.STATUS_RUNNING
