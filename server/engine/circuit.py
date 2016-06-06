import collections
import math
import numpy as np
import os
from shapely import geometry
from shapely import prepared
import sys


class Error(Exception):
  pass


class CircuitDoesNotExistError(Error):
  pass


_MAX_NUM_LAPS = 10

_PLUS_SPEED = 1
_MINUS_SPEED = 1
_TURN_ANGLE = math.pi / 4.0 + 0.0175  # Add small buffer of 1 degree.

_DIRECTIONS_WHEN_STOPPED = (
    np.array((-1, 0)),
    np.array((0, -1)),
    np.array((1, 0)),
    np.array((0, 1)),
    # np.array((0, 0)),  Player has to move.
)


# Stores a player state along the circuit.
STATUS_RUNNING = 0
STATUS_CRASHED = 1
STATUS_FINISHED = 2
STATUS_DISCONNECTED = 3


# Player state.
State = collections.namedtuple('State', ['xy', 'yaw', 'speed', 'round', 'lap', 'distance_left', 'status'])


class Circuit:
  circuit_data = None

  @staticmethod
  def SetPath(path):
    # List all circuit in the current folder and load them.
    for filename in (os.path.join(path, f) for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith('.ckt')):
      print 'Loading:', filename
      with open(filename) as fp:
        configuration = dict(l.strip().split(' = ', 1) for l in fp.readlines() if ' = ' in l)
        name = configuration['name']
        if name not in Circuit.circuit_data:
          # Keep backward compatibility.
          Circuit.circuit_data[name] = {
              'circuit_name': name,
              'circuit_grid_size': configuration['gridSize'] if 'gridSize' in configuration else 10,
              'circuit_maximum_speed': configuration['maximumSpeed'],
              'num_laps': int(configuration['numLaps']) if 'numLaps' in configuration else 1,
              'circuit_starting_line': [int(n) for n in configuration['startingLine'].split(',')],
              'circuit_inner_border': [int(n) for n in configuration['innerBorder'].split(',')],
              'circuit_outer_border': [int(n) for n in configuration['outerBorder'].split(',')],
          }

  @staticmethod
  def CircuitNames():
    return Circuit.circuit_data.keys()

  def __init__(self, name=None):
    try:
        data = Circuit.circuit_data[name if name else _DEFAULT_CIRCUIT_NAME]
    except KeyError:
        raise CircuitDoesNotExistError('%s does not exist.' % name)

    self.name = data['circuit_name']
    self.maximum_speed = float(data['circuit_maximum_speed'])
    self.grid_size = float(data['circuit_grid_size'])
    self.num_laps = data['num_laps']
    assert self.num_laps <= _MAX_NUM_LAPS, 'Cannot have more laps than %d.' % _MAX_NUM_LAPS
    # Starting line (LineString).
    line = np.array(data['circuit_starting_line']).astype(float)
    self.origin = line[:2]
    self.starting_line = _BuildLineString(line, origin=self.origin, resize=1.0 / self.grid_size)
    # Road (Polygon).
    self.raw_drivable_road = _BuildPolygonWithHole(
        data['circuit_outer_border'],
        data['circuit_inner_border'],
        resize=1.0 / self.grid_size,
        origin=self.origin)
    self.drivable_road_bounds = self.raw_drivable_road.bounds
    self.drivable_road = prepared.prep(self.raw_drivable_road)
    # Get valid starting points (list of numpy.array).
    self.starting_direction = self.GetStartingDirection()
    self.starting_points = self.GetStartingPoints()
    self.analyzer = None
    # Caches for OnRoad, CrossingLine and _GetNextPoints.
    self.onroad_cache = {}
    self.crossing_cache = {}
    self.next_points_cache = {}

  def Contains(self, point):
    return self.drivable_road.contains(geometry.Point(point))

  def OnRoad(self, xy1, xy2):
    key = (xy1[0], xy1[1], xy2[0], xy2[1])
    if key in self.onroad_cache:
      return self.onroad_cache[key]
    assert self.analyzer is not None, 'Call SetAnalyzer() before calling OnRoad().'
    ret = self.analyzer.Contains(xy2) and self.drivable_road.contains(geometry.LineString([xy1, xy2]))
    self.onroad_cache[key] = ret
    return ret

  def SetAnalyzer(self, analyzer):
    self.analyzer = analyzer

  def LapLength(self):
    assert self.analyzer is not None, 'Call SetAnalyzer() before calling LapLength().'
    return self.analyzer.MaxDistance()

  def Laps(self):
    return self.num_laps

  def IsStartingPoint(self, point):
    return tuple(point) in self.starting_points

  def GetStartingDirection(self):
    dp = np.array(self.starting_line.coords[0]) - np.array(self.starting_line.coords[1])
    return np.array([np.sign(dp[1]) if dp[1] else 0, -np.sign(dp[0]) if dp[0] else 0]).astype(int)

  def GetStartingPoints(self):
    points = set()
    direction = self.starting_direction
    direction = np.array([direction[1], -direction[0]])
    for i in range(int(self.starting_line.length)):
      if self.Contains(geometry.Point(direction * i)):
        points.add(tuple(direction * i))
    return points

  # Crossing excludes the xy1.
  def CrossingLine(self, xy1, xy2):
    key = (xy1[0], xy1[1], xy2[0], xy2[1])
    if key in self.crossing_cache:
      return self.crossing_cache[key]
    i = self.starting_line.intersection(geometry.LineString([xy1, xy2]))
    # There must be a single intersection point.
    if not isinstance(i, geometry.Point):
      ret = (0, 0)
    else:
      # Check distance between xy1 and intersection.
      i = np.array(i.coords[0])
      # Check direction of crossing.
      v = xy2 - xy1
      if v.dot(self.starting_direction) > 0:
        d = np.linalg.norm(i - xy1)
        if d < 0.5:  # Don't count if only the starting point crosses.
          ret = (0, 0)
        else:
          ret = (1, d / np.linalg.norm(v))  # We known ||v|| > 0
      else:  # This hysteresis is needed to avoid double counting.
        d = np.linalg.norm(i - xy2)
        if d < 0.5:  # Don't count if only the end point crosses.
          ret = (0, 0)
        else:
          ret = (-1, 0)
    self.crossing_cache[key] = ret
    return ret

  def _GetNextPoints(self, current_state):
    key = (current_state.xy[0], current_state.xy[1], current_state.yaw, current_state.speed)
    if key in self.next_points_cache:
      return self.next_points_cache[key]
    max_speed = min(self.maximum_speed, current_state.speed + _PLUS_SPEED)
    min_speed = max(0.5, current_state.speed - _MINUS_SPEED)  # Cars cannot stop.
    minx, miny, maxx, maxy = _BuildSearchBox(current_state, min_speed, max_speed)
    next_points = []
    for x in range(minx, maxx + 1):
      for y in range(miny, maxy + 1):
        xy = np.array((x, y))
        d = xy - current_state.xy
        new_yaw = math.atan2(d[1], d[0])
        new_speed = np.linalg.norm(d)
        da = _NormalizeAngle(new_yaw - current_state.yaw)
        if ((new_speed == 0 or (da <= _TURN_ANGLE and da >= -_TURN_ANGLE)) and new_speed <= max_speed and new_speed >= min_speed):
          # New status.
          new_status = STATUS_RUNNING if self.OnRoad(current_state.xy, xy) else STATUS_CRASHED
          # Check if we cross the line and in which direction.
          dlap, dround = self.CrossingLine(current_state.xy, xy)
          next_points.append((xy, new_yaw, new_speed, new_status, dlap, dround))
    self.next_points_cache[key] = next_points
    return next_points

  def GetNextStates(self, current_state=None, remove=()):
    assert self.analyzer is not None, 'Call SetAnalyzer() before calling GetNextStates().'
    # Start of race.
    next_states = []
    if current_state is None:
      d = self.starting_direction
      yaw = math.atan2(d[1], d[0])
      for p in self.starting_points:
        if p in remove or not self.analyzer.Contains(p):
          continue
        next_states.append(State(np.array(p), yaw, 0, 1, 0, self.analyzer.Distance(p), STATUS_RUNNING))
      return next_states
    # Only running states can move through the circuit.
    if current_state.status != STATUS_RUNNING:
      return []
    # Exception for the second turn.
    if current_state.round == 1:
      # We don't need to check remove here.
      p = current_state.xy + self.starting_direction
      next_states.append(State(p, current_state.yaw, 1, 2, 0, self.analyzer.Distance(p), STATUS_RUNNING))
      return next_states
    # Gathers next points first. The yaw and speed are calculated from those.
    if current_state.speed == 0.0:
      for xy in (current_state.xy + d for d in _DIRECTIONS_WHEN_STOPPED):
        if xy in remove:
          continue
        d = xy - current_state.xy
        new_speed = np.linalg.norm(d)
        new_yaw = math.atan2(d[1], d[0])
        # New status.
        new_status = STATUS_RUNNING if self.OnRoad(current_state.xy, xy) else STATUS_CRASHED
        # Check if we cross the line and in which direction.
        dlap, dround = self.CrossingLine(current_state.xy, xy)
        new_lap = current_state.lap + dlap
        if new_lap == self.num_laps:
          new_round = current_state.round + dround
          new_status = STATUS_FINISHED if new_status == STATUS_RUNNING else new_status
          new_distance = 0. if new_status == STATUS_FINISHED else current_state.distance_left
        else:
          new_round = current_state.round + 1
          new_distance = self.analyzer.Distance(xy) if new_status == STATUS_RUNNING else current_state.distance_left
        next_states.append(State(xy, new_yaw, new_speed, new_round, new_lap, new_distance, new_status))
      return next_states
    else:
      for next_point in self._GetNextPoints(current_state):
        xy, new_yaw, new_speed, new_status, dlap, dround = next_point
        if tuple(xy) in remove:
          continue
        new_lap = current_state.lap + dlap
        if new_lap == self.num_laps:
          new_round = current_state.round + dround
          new_status = STATUS_FINISHED if new_status == STATUS_RUNNING else new_status
          new_distance = 0. if new_status == STATUS_FINISHED else current_state.distance_left
        else:
          new_round = current_state.round + 1
          new_distance = self.analyzer.Distance(xy) if new_status == STATUS_RUNNING else current_state.distance_left
        next_states.append(State(xy, new_yaw, new_speed, new_round, new_lap, new_distance, new_status))
      return next_states

  def ScaleStates(self, states):
    scaled_states = []
    for state in states:
      p = state.xy.astype(float) * self.grid_size + self.origin
      scaled_states.append(State(p, state.yaw, state.speed, state.round, state.lap, state.distance_left, state.status))
    return scaled_states

  def ScaleTuples(self, states):
    scaled_states = []
    for state in states:
      p = np.array(state).astype(float) * self.grid_size + self.origin
      scaled_states.append(tuple(p))
    return scaled_states

  def JSONData(self):
    return Circuit.circuit_data[self.name]

  def Print(self, states=None):
    bounds = tuple(int(b) for b in self.drivable_road_bounds)
    line_char = '-' if self.starting_direction[0] == 0 else '|'
    states = set([tuple(m.xy) for m in states]) if states else set()
    for y in range(bounds[1] - 1, bounds[3] + 2):  # Add a margin.
      for x in range(bounds[0] - 1, bounds[2] + 2):  # Add a margin.
        p = np.array([x, y])
        sys.stdout.write(
            '+' if tuple(p) in states else
            line_char if self.IsStartingPoint(p) else
            ' ' if self.Contains(p) else
            'x')
      sys.stdout.write('\n')
    sys.stdout.flush()


def _BuildSearchBox(state, min_speed, max_speed):
  minx = min_speed
  maxx = max_speed
  maxy = math.sin(_TURN_ANGLE) * maxx
  miny = -maxy
  # Rotate.
  box = np.array([[minx, miny], [minx, maxy], [maxx, miny], [maxx, maxy]])
  rotation = np.array([[math.cos(state.yaw), math.sin(state.yaw)], [-math.sin(state.yaw), math.cos(state.yaw)]])
  rbox = box.dot(rotation).astype(int) + state.xy
  # Get bounds.
  return (np.min(rbox[:, 0]), np.min(rbox[:, 1]), np.max(rbox[:, 0]), np.max(rbox[:, 1]))


def _BuildPolygonWithHole(outer, inner, origin=np.array((0, 0)), resize=1.):
  outer = np.array([(outer[i], outer[i + 1]) for i in xrange(0, len(outer), 2)]) - origin
  inner = np.array([(inner[i], inner[i + 1]) for i in xrange(0, len(inner), 2)]) - origin
  outer *= resize
  inner *= resize
  return geometry.Polygon(outer, [inner])


def _BuildLineString(points, origin=np.array((0, 0)), resize=1.):
  points = (np.array([(points[i], points[i + 1]) for i in xrange(0, len(points), 2)]) - origin) * resize
  return geometry.LineString(points)


def _NormalizeAngle(angle):
    while angle > math.pi:
      angle -= 2. * math.pi
    while angle < -math.pi:
      angle += 2. * math.pi
    return angle


_DEFAULT_CIRCUIT_NAME = 'Patatoid'

# Format is kept almost identical to the original CirKuit 2D game.
# Only load one circuit from code.
Circuit.circuit_data = {
    'Patatoid': {
        'circuit_name': 'Patatoid',
        'circuit_grid_size': 10,
        'circuit_maximum_speed': 6,
        'num_laps': 1,
        'circuit_starting_line': [226, 236, 100, 236],
        'circuit_inner_border': [217, 95, 275, 110, 319, 120, 331, 153, 335, 191, 331, 236, 292, 295, 265, 316, 230, 320, 193, 316, 173, 288, 167, 272, 186, 236, 219, 208, 232, 185, 269, 116],
        'circuit_outer_border': [323, 44, 363, 76, 399, 79, 427, 93, 445, 126, 447, 185, 442, 245, 369, 324, 301, 356, 227, 357, 175, 355, 141, 320, 117, 289, 122, 254, 154, 148, 217, 158, 154, 141, 182, 71, 225, 41, 279, 32],
    },
}


_PRINT_SIZE = 25
