from __future__ import print_function

import time
import threading

import util


_TIMEOUT = 90  # Allow 1.5 minutes (the HTML UI actually allows only 60 seconds, but we give some slack).


class Error(Exception):
  pass


class HumanNotPlayingError(Error):
  pass


class Player(object):

  def __init__(self):
    self.state = None
    self.state_lock = util.RWLock()
    self.done = False
    self.done_lock = util.RWLock()
    self.trajectory = []
    self.trajectory_lock = util.RWLock()

  def Play(self, circuit, players):
    raise NotImplementedError('Cannot call Play() directly on Player.')

  def SetAllowedMoves(self, circuit, players):
    player_states = [p.GetState() for p in players]
    with self.state_lock(util.READ_LOCKED):
      my_state = self.state
    self.allowed_moves = Player.ComputeAllowedMoves(circuit, my_state, player_states)

  @staticmethod
  def ComputeAllowedMoves(circuit, state, player_states):
    next_round = state.round + 1 if state else 1
    # Prevent player from crashing with other players.
    forbidden_positions = set()
    for state_other in player_states:
      if state_other and state_other.round == next_round:
        forbidden_positions.add((state_other.xy[0], state_other.xy[1]))
    return circuit.GetNextStates(current_state=state, remove=forbidden_positions)

  def GetAllowedMoves(self):
    return self.allowed_moves

  def Stop(self, forced=False):
    with self.done_lock(util.WRITE_LOCKED):
      self.done = True

  def IsStopped(self):
    with self.done_lock(util.READ_LOCKED):
      return self.done

  def SetState(self, state):
    if self.IsStopped():
      return
    with self.state_lock(util.WRITE_LOCKED):
      with self.trajectory_lock(util.WRITE_LOCKED):
        self.state = state
        self.trajectory.append(tuple(state.xy))

  def GetState(self):
    with self.state_lock(util.READ_LOCKED):
      return self.state

  def GetTrajectory(self):
    with self.trajectory_lock(util.READ_LOCKED):
      return self.trajectory[-6:]  # Provide last 5 moves.


class HumanPlayer(Player):

  def __init__(self):
    # The next move variable is accessed concurrently.
    self.condition = threading.Condition(threading.Lock())
    self.next_move = None
    self.is_playing = False
    self.is_playing_lock = util.RWLock()
    Player.__init__(self)

  def Play(self, circuit, players):
    # This function waits until a move has been populated.
    is_done = False
    self.condition.acquire()
    with self.state_lock(util.WRITE_LOCKED):
      self.is_playing = True
    # TODO: Set timeout after 60 seconds.
    self.start_time = int(time.time())
    while self.next_move is None:
      self.condition.wait(2.)  # Timeout of 2 seconds.
      if int(time.time()) - self.start_time > _TIMEOUT:
        self.Stop(forced=True)  # This does not throw Exceptions.
      with self.done_lock(util.READ_LOCKED):
        is_done = self.done
      if is_done:  # Requested to stop.
        break
    next_move = None if is_done else self.next_move
    self.next_move = None
    self.condition.release()
    return next_move

  def SetNextMove(self, move_index):
    is_playing = self.IsPlaying()
    if not is_playing:
      raise HumanNotPlayingError('Human player is not allowed to play yet.')
    self.condition.acquire()
    self.next_move = move_index
    with self.state_lock(util.WRITE_LOCKED):
      self.is_playing = False
    self.condition.notify()
    self.condition.release()

  def IsPlaying(self):
    with self.state_lock(util.READ_LOCKED):
      return self.is_playing


####################
# Computer player. #
####################

computer_player_registry = {}


def RegisterPlayer(cls):
  if cls.__name__ == 'ComputerPlayer':
    return
  computer_player_registry[cls.__name__] = cls
  print('Registered', cls.__name__, 'as computer player.')


def CreatePlayer(cls_name):
  return computer_player_registry[cls_name]()


def ListComputerPlayers():
  return computer_player_registry.keys()


class ComputerPlayerMeta(type):
    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        RegisterPlayer(cls)
        return cls


class ComputerPlayer(Player):
  __metaclass__ = ComputerPlayerMeta

  def __init__(self):
    Player.__init__(self)

  def Play(self, circuit, players):
    raise NotImplementedError('Cannot call Play() directly on ComputerPlayer.')
