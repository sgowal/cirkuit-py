from __future__ import print_function

import collections
import heapq
import math
import random
import sys
import time

# For test (ugly as hell).
if __name__ == '__main__':
  sys.path.append('..')
  import argparse
  import itertools
  import matplotlib.pyplot as plt
  import numpy as np
  import circuit_analyzer
  from circuit import Circuit

from circuit import STATUS_CRASHED
from circuit import STATUS_FINISHED
from circuit import State
from player import ComputerPlayer


_YAW_RESOLUTION = 12. / math.pi  # 15 degrees.
_SPEED_RESOLUTION = 1. / 0.5
_INFINITY = float(sys.maxint) / 4.
_ASTAR_FACTOR = 1.5  # Try to explore less states (the larger the faster but worse solution).
_LENGTH_TO_LAP_FACTOR = 1. / 4. * _ASTAR_FACTOR  # 1/5 is the average number of turns for a given length.
_MAX_DEPTH = 8
_EPSILON = 1e-3


class ApproximateState(State):

  def __hash__(self):
    # The following info is enough to make the state unique (modulo the round number).
    # Note that self.yaw is always between -pi and pi.
    return hash((self.xy[0], self.xy[1], _Binarize(self.yaw, _YAW_RESOLUTION), _Binarize(self.speed, _SPEED_RESOLUTION), self.lap))

  def __eq__(self, other):
    return (self.xy[0], self.xy[1], _Binarize(self.yaw, _YAW_RESOLUTION), _Binarize(self.speed, _SPEED_RESOLUTION), self.lap) == (other.xy[0], other.xy[1], _Binarize(other.yaw, _YAW_RESOLUTION), _Binarize(other.speed, _SPEED_RESOLUTION), other.lap)

  def __lt__(self, other):
    return False  # Always return false.


# Keep impossible state as a marker for removed entries.
_REMOVED = ApproximateState((0, 0), 0, 0, 0, -1000, 0, 0)  # -1000 laps.


class AStarPlayer(ComputerPlayer):

  def __init__(self):
    ComputerPlayer.__init__(self)

  def Play(self, circuit, players, plot=False):
    def heuristic(state):
      if state.status == STATUS_FINISHED:
        delta = float(state.round) - float(int(state.round))
        return (delta - 1.) if delta > _EPSILON else 0.
      if state.status == STATUS_CRASHED:
        return _INFINITY
      return (float(circuit.Laps() - state.lap - 1) * circuit.LapLength() + state.distance_left) * _LENGTH_TO_LAP_FACTOR

    start_time = time.clock()

    # Slightly modified A* that expands only up to a given depth.
    # Note that we also combine with Hybrid-A* to avoid exploring too many continuous states.
    explored_states = 0
    best_state = None  # Remember best seen state (lowest f_score at max depth).
    best_score = None
    closed_set = set()
    open_set = [ApproximateState(*s) for s in self.allowed_moves]  # Keep order.
    g_score = collections.defaultdict(lambda: _INFINITY)  # Cost of going from start to state.
    came_from = {}  # To reconstruct the path.
    start_indices = {}  # To grab the best index.
    entry_finder = {}
    for i, s in enumerate(open_set):
      start_indices[s] = i
      entry_finder[s] = [1. + heuristic(s), 0, s]
      g_score[s] = 1.
    open_set = set(open_set)
    queue = [entry_finder[s] for s in open_set]  # Triplet of <f_score, depth, state>.
    heapq.heapify(queue)  # Keep the lowest f_score at easy reach.

    while open_set:
      f_score, depth, current = heapq.heappop(queue)  # Grab state with lowest f_score.
      if current == _REMOVED:  # Ignore updated.
        continue
      entry_finder.pop(current)
      open_set.remove(current)
      closed_set.add(current)
      explored_states += 1

      if current.status == STATUS_FINISHED or depth == _MAX_DEPTH:
        best_state = current
        best_score = f_score
        break

      for next_state in (ApproximateState(*s) for s in circuit.GetNextStates(current)):
        if next_state in closed_set:
          continue

        tentative_gscore = g_score[current] + 1.
        tentative_fscore = tentative_gscore + heuristic(next_state)
        if next_state not in open_set:
          pass
        elif tentative_gscore >= g_score[next_state]:  # Not better.
          continue
        else:
          # It is already in the open_set but with a higher score. Update it.
          entry = entry_finder.pop(next_state)
          entry[-1] = _REMOVED  # Remove reference to state in queue.

        # It's pushed so update score maps :)
        new_entry = [tentative_fscore, depth + 1, next_state]
        open_set.add(next_state)
        entry_finder[next_state] = new_entry
        heapq.heappush(queue, new_entry)
        g_score[next_state] = tentative_gscore
        came_from[next_state] = current
    # We are done.
    end_time = time.clock()
    print('Best final state with score =', best_score, 'found in %.2f ms' % ((end_time - start_time) * 1000.))
    print('Explored', explored_states, 'states.')
    if best_state is None:
      return random.choice(xrange(len(self.allowed_moves)))

    # Plot.
    if plot:
      plt.plot(circuit.raw_drivable_road.exterior.xy[0], circuit.raw_drivable_road.exterior.xy[1], 'k', linewidth=2)
      plt.plot(circuit.raw_drivable_road.interiors[0].xy[0], circuit.raw_drivable_road.interiors[0].xy[1], 'k', linewidth=2)
      plt.plot(circuit.starting_line.xy[0], circuit.starting_line.xy[1], 'k', linewidth=2)
      valid_points = [p for p in circuit.analyzer.distances]
      valid_points = np.array(valid_points).astype(float)
      plt.scatter(valid_points[:, 0], valid_points[:, 1], c='gray', marker='+')
      for e, s in itertools.islice(came_from.iteritems(), 1000):  # Plot max 1000.
        plt.plot([s.xy[0], e.xy[0]], [s.xy[1], e.xy[1]], 'b+--', linewidth=2)
      if best_state:
        current = best_state
        path = collections.deque([current])
        while current in came_from:
          print('Backtrack:', current, '- g_score =', g_score[current])
          current = came_from[current]
          path.appendleft(current)
        print('Backtrack:', current, '- g_score =', g_score[current])
        path_points = np.array([s.xy for s in path])
        plt.plot(path_points[:, 0], path_points[:, 1], 'g', linewidth=2)
      plt.axis('equal')
      plt.show()

    current = best_state
    if current in start_indices:
      return start_indices[current]
    while current in came_from:
      current = came_from[current]
      if current in start_indices:
        return start_indices[current]
    return None


def _Binarize(value, resolution):
  return int(value * resolution)


def _ConvertLengthToRounds(value):
  return value * _LENGTH_TO_LAP_FACTOR


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--circuit_directory", metavar='DIRECTORY', type=str, required=False, help="The directory where the circuit files are located.")
  parser.add_argument("--circuit_name", metavar='NAME', type=str, required=False, help="The name of the circuit to analyze.")
  parser.add_argument("--plot", type=bool, default=True, help="Whether to plot the analysis.")
  args = parser.parse_args()
  if args.circuit_directory:
    Circuit.SetPath(args.circuit_directory)
  circuit = circuit_analyzer.GetAnalyzableCircuit(args.circuit_name)
  p = AStarPlayer()
  p.SetAllowedMoves(circuit, [])
  index = p.Play(circuit, [], plot=args.plot)
  print('Best index:', index)
  print('Re-running a second time to test caching...')
  index = p.Play(circuit, [], plot=False)
