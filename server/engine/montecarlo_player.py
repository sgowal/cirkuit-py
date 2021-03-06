from __future__ import print_function

import multiprocessing
import random
import time

# For test (ugly as hell).
if __name__ == '__main__':
  import sys
  sys.path.append('..')
  sys.path.append('../util')
  import argparse
  import circuit_analyzer
  from circuit import Circuit

from circuit import STATUS_CRASHED
from circuit import STATUS_FINISHED
from player import ComputerPlayer

# xrange compatibility.
try:
    xrange
except NameError:
    xrange = range


# A depth of 2 will expand the moves 3 times (0 -> direct moves, 1 -> lookahead of 1 move, ...)
_MAX_DEPTH = 6
_NUM_RANDOM_PLAY_PER_THREAD = 400
_NUM_THREADS = 8
_MINIMUM_SCORE = -1e6
_CRASH_SCORE = 1e6


class MonteCarloPlayer(ComputerPlayer):

  def __init__(self):
    ComputerPlayer.__init__(self)

  def Play(self, circuit, players):
    # Run multiple threads and pick the best.
    start_time = time.clock()
    if _NUM_THREADS > 1:
      pool = multiprocessing.Pool(processes=_NUM_THREADS)
      results = pool.map(_GetBestMove, [(self.allowed_moves, circuit)] * _NUM_THREADS)
      score, move_index = min(results)
      pool.terminate()
    else:
      score, move_index = _GetBestMove((self.allowed_moves, circuit))
    end_time = time.clock()
    print('Best final state with score =', score, 'found in %.2f ms' % ((end_time - start_time) * 1000.))
    print('Best score found with depth %d:' % _MAX_DEPTH, score)
    return move_index


def _Done(state):
  return state.status == STATUS_FINISHED or state.status == STATUS_CRASHED


def _GetDistanceScore(circuit, state):
    return float(circuit.Laps() - state.lap - 1) * circuit.LapLength() + state.distance_left


def _GetBestMove(argument):
  states, circuit = argument
  best_index = None
  best_score = None
  for _ in xrange(_NUM_RANDOM_PLAY_PER_THREAD):
    # Pick first move at random and remember index.
    index = random.choice(xrange(len(states)))
    current_state = states[index]
    if not _Done(current_state):
      for _ in xrange(_MAX_DEPTH):
        # We don't care about the other players beyond the first depth.
        next_states = circuit.GetNextStates(current_state)
        current_state = next_states[random.choice(xrange(len(next_states)))]
        if _Done(current_state):
          break
    if current_state.status == STATUS_CRASHED:
      score = _GetDistanceScore(circuit, current_state) + _CRASH_SCORE
    elif current_state.status == STATUS_FINISHED:
      score = float(current_state.round) + _MINIMUM_SCORE
    else:
      score = _GetDistanceScore(circuit, current_state)
    if best_index is None or score < best_score:  # Smaller is better.
      best_index = index
      best_score = score
  return best_score, best_index


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--circuit_directory", metavar='DIRECTORY', type=str, required=False, help="The directory where the circuit files are located.")
  parser.add_argument("--circuit_name", metavar='NAME', type=str, required=False, help="The name of the circuit to analyze.")
  args = parser.parse_args()
  if args.circuit_directory:
    Circuit.SetPath(args.circuit_directory)
  circuit = circuit_analyzer.GetAnalyzableCircuit(args.circuit_name)
  p = MonteCarloPlayer()
  p.SetAllowedMoves(circuit, [])
  index = p.Play(circuit, [])
  # print 'Best index:', index
  # print 'Re-running a second time to test caching...'
  index = p.Play(circuit, [])
