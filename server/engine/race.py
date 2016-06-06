import random
import threading

import circuit
import circuit_analyzer
import util


class RaceThread(threading.Thread):

  def __init__(self, race_handle):
    self.race_handle = race_handle
    self.circuit = self.race_handle.circuit
    self.players = self.race_handle.players
    threading.Thread.__init__(self)
    # Create valid first turn snapshot.
    # That is the player to play and its moves are set correctly.
    self.race_handle.player_to_play = 0
    self.players[0].SetAllowedMoves(self.circuit, self.players)

  def run(self):
    # Make player_instance take turns and stop when there is a
    # winner or race_handle.must_stop is True.
    print 'Race started'
    self.race_handle.must_stop_lock.acquire_read()
    while not self.race_handle.must_stop:
      self.race_handle.must_stop_lock.release()
      # Play current player. We do not need to lock since this thread is
      # the only one that writes to player_to_player.
      print 'Player now playing:', self.race_handle.player_to_play
      player_instance = self.players[self.race_handle.player_to_play]
      allowed_moves = player_instance.GetAllowedMoves()
      # If there are no allowed moves, the player has crashed...
      move_index = player_instance.Play(self.circuit, self.players) if allowed_moves else None
      # Update race snapshot atomically.
      self.race_handle.snapshot_lock.acquire_write()
      # Update player state.
      if move_index is None or move_index < 0 or move_index >= len(allowed_moves):
        player_instance.Stop(forced=True)
      else:
        player_instance.SetState(allowed_moves[move_index])
        if allowed_moves[move_index].status != circuit.STATUS_RUNNING:
          player_instance.Stop()
      # Find next player.
      self.race_handle.player_to_play = (self.race_handle.player_to_play + 1) % len(self.players)
      original_player_to_play = self.race_handle.player_to_play
      must_stop = False
      player_instance = self.players[self.race_handle.player_to_play]
      while player_instance.IsStopped():
        self.race_handle.player_to_play = (self.race_handle.player_to_play + 1) % len(self.players)
        player_instance = self.players[self.race_handle.player_to_play]
        if original_player_to_play == self.race_handle.player_to_play:
          # All players are done, stop.
          must_stop = True
          break
      if must_stop:
        print 'Stopping race...'
        self.race_handle.must_stop_lock.acquire_write()
        self.race_handle.must_stop = True
        self.race_handle.must_stop_lock.release()
        self.race_handle.player_to_play = None
        self.race_handle.snapshot_lock.release()
        self.race_handle.must_stop_lock.acquire_read()
        continue
      self.players[self.race_handle.player_to_play].SetAllowedMoves(self.circuit, self.players)
      self.race_handle.snapshot_lock.release()
      self.race_handle.must_stop_lock.acquire_read()
    self.race_handle.must_stop_lock.release()
    print 'Race is finished'


class Race(object):

  def __init__(self, circuit_name=None):
    self.circuit = circuit_analyzer.GetAnalyzableCircuit(circuit_name)
    self.must_stop_lock = util.RWLock()
    self.must_stop = False
    self.snapshot_lock = util.RWLock()
    self.player_to_play = None
    self.players = []
    self.thread = None

  def Start(self, players):
    assert self.thread is None, 'Cannot start the same race twice.'
    # Setup players.
    self.unshuffled_players = players
    self.players = players[:]
    random.shuffle(self.players)
    # Starts the race and returns immediately.
    self.thread = RaceThread(self)
    self.thread.start()

  def Stop(self):
    # Force stop the race thread.
    with self.must_stop_lock(util.WRITE_LOCKED):
      self.must_stop = True
      for player_instance in self.players:
        player_instance.Stop(forced=True)

  def GetCircuit(self):
    return self.circuit

  def GetSnapshot(self):
    # Report the available moves of that player and whether it's playing.
    with self.snapshot_lock(util.READ_LOCKED):
      return {
          'states': [p.GetState() for p in self.unshuffled_players],
          'playing': self.players[self.player_to_play] if self.player_to_play is not None else None,
          'moves': self.circuit.ScaleStates(self.players[self.player_to_play].GetAllowedMoves()) if self.player_to_play is not None else None,
          'trajectories': [self.circuit.ScaleTuples(p.GetTrajectory()) for p in self.unshuffled_players],
      }
