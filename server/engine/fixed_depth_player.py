from circuit import STATUS_CRASHED
from circuit import STATUS_FINISHED
from player import ComputerPlayer


# A depth of 2 will expand the moves 3 times (0 -> direct moves, 1 -> lookahead of 1 move, ...)
_MAX_DEPTH = 2
_MINIMUM_SCORE = -1e6
_CRASH_SCORE = 1e6


class FixedDepthPlayer(ComputerPlayer):

  def __init__(self):
    ComputerPlayer.__init__(self)

  def Play(self, circuit, players):
    move_index, score = _GetBestMove(self.allowed_moves, circuit, _MAX_DEPTH)
    print 'Best score found with depth %d:' % _MAX_DEPTH, score
    return move_index


def _GetDistanceScore(circuit, state):
    return float(circuit.Laps() - state.lap - 1) * circuit.LapLength() + state.distance_left


def _GetBestMove(states, circuit, depth):
  best_index = None
  best_score = None
  for i, state in enumerate(states):
    if state.status == STATUS_CRASHED:
      score = _GetDistanceScore(circuit, state) + _CRASH_SCORE
    elif state.status == STATUS_FINISHED:
      score = float(state.round) + _MINIMUM_SCORE
    elif depth == 0:
      score = _GetDistanceScore(circuit, state)
    else:
      # We don't care about the other players beyond the first depth.
      next_states = circuit.GetNextStates(state)
      _, score = _GetBestMove(next_states, circuit, depth - 1)
      if score is None:
        continue
    if best_index is None or score < best_score:  # Smaller is better.
      best_index = i
      best_score = score
  return best_index, best_score
