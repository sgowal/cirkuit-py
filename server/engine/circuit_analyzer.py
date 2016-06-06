import collections
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
from scipy import spatial
from scipy import interpolate
from shapely import geometry
from shapely import prepared

import circuit
import util

_OFFSET_FACTOR = 0.1  # Must be strictly smaller than 1/3.
_EXTRA_LENGTH = _OFFSET_FACTOR * 3.  # Compensation for slightly offsetting the finish point.
_EPSILON = 1e-5

analyzer_instances = {}
analyzer_instances_lock = util.RWLock()


def GetAnalyzer(name=None, plot=False):
    if name is None:
      name = circuit._DEFAULT_CIRCUIT_NAME
    with analyzer_instances_lock(util.READ_LOCKED):
      if name in analyzer_instances:
        analyzer = analyzer_instances[name]
      else:
        analyzer_instances_lock.promote()  # Write locked.
        analyzer = CircuitAnalyzer(circuit.Circuit(name), plot=plot)
        analyzer_instances[name] = analyzer
    return analyzer


def GetAnalyzableCircuit(name=None):
  print 'Loading circuit:', name
  circuit_analyzer = GetAnalyzer(name)
  circuit_analyzer.circuit.SetAnalyzer(circuit_analyzer)
  return circuit_analyzer.circuit


class CircuitAnalyzer(object):

  def __init__(self, circuit, plot=False):
    # Construct mapping from each valid circuit point to the distance to the finish.
    self.circuit = circuit
    self._BuildDistanceMap(plot=plot)

  def Distance(self, point):
    return self.distances[tuple(point)]

  def Contains(self, point):
    return tuple(point) in self.distances

  def MaxDistance(self):
    return self.max_distance

  def _BuildDistanceMap(self, plot=False):
    # First, build the polygon that is cut by the starting line.
    start_direction = self.circuit.GetStartingDirection().astype(float)
    cut_interior = _CutLineRing(self.circuit.raw_drivable_road.interiors[0], self.circuit.starting_line, start_direction)
    cut_exterior = _CutLineRing(self.circuit.raw_drivable_road.exterior, self.circuit.starting_line, start_direction)
    polygon = geometry.Polygon(list(cut_interior.coords) + list(reversed(list(cut_exterior.coords))))
    if not polygon.exterior.is_simple and plot:
      plt.plot(polygon.exterior.xy[0], polygon.exterior.xy[1], 'k', linewidth=2)
      plt.axis('equal')
      plt.show()
    assert polygon.exterior.is_simple, 'Ooops.'

    # Place starting and finishing points.
    middle_start = (np.array(cut_interior.coords[0]) + np.array(cut_exterior.coords[0]) + np.array(cut_interior.coords[-1]) + np.array(cut_exterior.coords[-1])) / 4.
    finish_point = middle_start - start_direction * _OFFSET_FACTOR * 1.5

    # Convert polygon to numpy array.
    points = np.empty((len(polygon.exterior.coords), 2))
    for i in range(len(polygon.exterior.coords)):
      points[i, 0] = polygon.exterior.coords[i][0]
      points[i, 1] = polygon.exterior.coords[i][1]

    # Make triangulation.
    # TODO: Find the option of qhull that will keep only the triangles inside the polygon.
    #       Also at the moment it can delete the point at the boundary (which is not ideal).
    triangles = spatial.Delaunay(points)
    # Mark triangles that are outside the polygon as invalid.
    polygon = prepared.prep(polygon)
    polys = []
    polys_center = []  # The inside polygon check is faster and more robust if we take the center.
    finish_triangle_index = None
    for i, triangle in enumerate(triangles.simplices):
      polys.append(geometry.Polygon(points[triangle]))
      polys_center.append(geometry.Point(np.mean(points[triangle], axis=0)))
      if finish_triangle_index is None and polys[-1].contains(geometry.Point(finish_point)):
        finish_triangle_index = i
    valid = np.array(map(polygon.contains, polys_center)).astype(bool)
    assert finish_triangle_index is not None, 'Ooops'
    # Map each point on the grid to a triangle.
    bounds = tuple(int(b) for b in self.circuit.drivable_road_bounds)
    point_to_triangle = {}
    for x in range(bounds[0], bounds[2] + 1):
      for y in range(bounds[1], bounds[3] + 1):
        p = (x, y)
        for i, t in enumerate(polys):
          if valid[i] and t.contains(geometry.Point(p)):
            point_to_triangle[p] = i

    # We build the adjacency list (it also holds the edge information).
    # This adjacency list must be a tree (since we do not have holes inside the road).
    adjacency_lists = {}
    for i in range(len(triangles.simplices)):
      if not valid[i]:
        continue
      adjacency_lists[i] = []
      for n in (n for n in triangles.neighbors[i] if n >= 0 and valid[n]):
        # Purposefully store edge backwards.
        adjacency_lists[i].append(_BuildEdge(n, i, triangles.simplices, points))
    # Find the path from any node to the finish (BFS or DFS would do - use DFS).
    # We effectively build a tree that stores the parent relationship that lead a leaf triangle to the root triangle (where the finish point is).
    triangle_tree = {}
    triangle_tree[finish_triangle_index] = None  # Sentinel.
    visited = np.zeros(len(triangles.simplices)).astype(bool)  # Since we have both forward and backward edges, we still need to be careful.
    stack = [finish_triangle_index]
    while stack:
      u = stack.pop()
      visited[u] = True
      if u not in adjacency_lists:
        continue
      for edge in adjacency_lists[u]:
        if visited[edge.start.id]:
          continue
        triangle_tree[edge.start.id] = edge  # Note that edge is was reversed and hence it is in the correct direction now.
        stack.append(edge.start.id)

    # Find the shortest path from each valid point to the finish.
    try:
      self.distances = {}
      self.max_distance = 0
      for point, start_triangle_index in point_to_triangle.iteritems():
        self.distances[point] = _FindDistance(np.array(point), start_triangle_index, finish_point, triangle_tree) + _EXTRA_LENGTH
        self.max_distance = max(self.max_distance, self.distances[point])
    except KeyError as e:
      if plot:
        print 'Error while processing circuit, but trying to continue anyways...'
      else:
        raise e

    if plot:
      # Plot distance.
      if self.distances:
        x = []
        y = []
        z = []
        for k, v in self.distances.iteritems():
          x.append(k[0])
          y.append(k[1])
          z.append(v)
        datapoints = np.array((x, y)).T
        z = np.array(z)
        XI, YI = np.meshgrid(range(bounds[0], bounds[2] + 1), range(bounds[1], bounds[3] + 1))
        ZI = interpolate.griddata(datapoints, z, (XI, YI), method='nearest')
        cmap = plt.get_cmap('RdYlGn_r')
        im = plt.imshow(ZI, cmap=cmap, interpolation='nearest', origin='lower',
                        extent=[bounds[0] - 0.5, bounds[2] + 0.5, bounds[1] - 0.5, bounds[3] + 0.5])
        # Mask outside road.
        plt.gca().add_patch(Polygon(self.circuit.raw_drivable_road.interiors[0].coords, facecolor='white', edgecolor='none'))
        patch = Polygon(self.circuit.raw_drivable_road.exterior.coords, facecolor='none')
        plt.gca().add_patch(patch)
        im.set_clip_path(patch)

      # Plot triangles.
      plt.plot(points[:, 0], points[:, 1], 'k--', linewidth=2)
      plt.plot(finish_point[0], finish_point[1], 'ro')
      plt.triplot(points[:, 0], points[:, 1], triangles.simplices[valid].copy())
      for edge in triangle_tree.itervalues():
        if edge is None:
          continue
        plt.plot([edge.start.xy[0], edge.end.xy[0]], [edge.start.xy[1], edge.end.xy[1]], 'c--')
        plt.plot([edge.gate.left.xy[0]], [edge.gate.left.xy[1]], 'r+')
        plt.plot([edge.gate.right.xy[0]], [edge.gate.right.xy[1]], 'b+')
      # Plot grid.
      valid_points = []
      for x in range(bounds[0], bounds[2] + 1):
        for y in range(bounds[1], bounds[3] + 1):
          p = (x, y)
          if p in self.distances:
            valid_points.append(p)
      if valid_points:
        valid_points = np.array(valid_points).astype(float)
        plt.scatter(valid_points[:, 0], valid_points[:, 1], c='gray', marker='+')
      plt.axis('equal')
      plt.show()


####################################################
# Helper classes to describe the exploration graph #
####################################################

class Edge(object):

  def __init__(self, start, end, gate):
    self.start = start
    self.end = end
    self.gate = gate

  def __eq__(self, other):
    # No need to compare the gate since it should be the same by construction.
    return self.start == other.start and self.end == other.end


class Gate(object):

  def __init__(self, left, right):
    self.left = left
    self.right = right

  def __eq__(self, other):
    self.left == other.left and self.right == other.right


class Point(object):

  def __init__(self, id, xy):
    self.id = id
    self.xy = xy

  def __eq__(self, other):
    # Only comparing ids if either one is not None.
    if self.id is not None or self.id is not None:
      return self.id == other.id
    return np.all(self.xy == other.xy)


######################
# Find shortest path #
######################

def _FindDistance(start_point, start_triangle_index, finish_point, triangle_tree):
  # Algorithm from https://skatgame.net/mburo/ps/thesis_demyen_2006.pdf
  funnel = Funnel(Point(None, start_point), start_triangle_index)
  path = funnel.GetShortestPath(triangle_tree, Point(None, finish_point))
  # Compute distance.
  distance = 0.
  for i in range(len(path) - 1):
    distance += np.linalg.norm(path[i + 1].xy - path[i].xy)
  return distance


# TODO: Simplify the following code. In particular, we should be able to assume that the
# left and right point of each gate are correct.
class Funnel(object):

  def __init__(self, start, start_triangle_index):
    self.start = start
    self.start_triangle_index = start_triangle_index
    self.left_funnel = collections.deque([start])
    self.right_funnel = collections.deque([start])
    self.shortest_path = []

  def GetShortestPath(self, search_tree, goal):
    current_triangle_index = self.start_triangle_index
    while search_tree[current_triangle_index]:
      self._AddGate(search_tree[current_triangle_index].gate)
      current_triangle_index = search_tree[current_triangle_index].end.id
    self._AddPoint(goal)
    return self.shortest_path

  def PrintFunnels(self):
    print [p.id for p in self.left_funnel], [p.id for p in self.right_funnel]

  def _AddGate(self, gate):
    diag_right = gate.right
    diag_left = gate.left
    # Start.
    if len(self.left_funnel) == 1 and len(self.right_funnel) == 1:
      self.left_funnel.append(diag_left)
      self.right_funnel.append(diag_right)
      return
    if len(self.left_funnel) + len(self.right_funnel) == 3:
      if len(self.left_funnel) == 2:
        if self.left_funnel[-1] == diag_left:
          self._CheckFunnel(False, diag_right)
          return
        if self.left_funnel[-1] == diag_right:
          self._CheckFunnel(False, diag_left)
          return
        if self.left_funnel[0] == diag_left:
          self.left_funnel.pop()
          self.left_funnel.append(diag_right)
          return
        if self.left_funnel[0] == diag_right:
          self.left_funnel.pop()
          self.left_funnel.append(diag_left)
          return
      else:
        if self.left_funnel[0] == diag_left:
          self.right_funnel.clear()
          self.right_funnel.append(self.left_funnel[0])
          self.right_funnel.append(diag_right)
          return
        if self.left_funnel[0] == diag_right:
          self.right_funnel.clear()
          self.right_funnel.append(self.left_funnel[0])
          self.right_funnel.append(diag_left)
          return
      # Symmetric version of the above.
      if len(self.right_funnel) == 2:
        if self.right_funnel[-1] == diag_left:
          self._CheckFunnel(True, diag_right)
          return
        if self.right_funnel[-1] == diag_right:
          self._CheckFunnel(True, diag_left)
          return
        if self.right_funnel[0] == diag_left:
          self.right_funnel.pop()
          self.right_funnel.append(diag_right)
          return
        if self.right_funnel[0] == diag_right:
          self.right_funnel.pop()
          self.right_funnel.append(diag_left)
          return
      else:
        if self.right_funnel[0] == diag_left:
          self.left_funnel.clear()
          self.left_funnel.append(self.right_funnel[0])
          self.left_funnel.append(diag_right)
          return
        if self.right_funnel[0] == diag_right:
          self.left_funnel.clear()
          self.left_funnel.append(self.right_funnel[0])
          self.left_funnel.append(diag_left)
          return
    if self.left_funnel[-1] == diag_left:
      self._CheckFunnel(False, diag_right)
      return
    if self.left_funnel[-1] == diag_right:
      self._CheckFunnel(False, diag_left)
      return
    if self.right_funnel[-1] == diag_left:
      self._CheckFunnel(True, diag_right)
      return
    self._CheckFunnel(True, diag_left)

  def _AddPoint(self, target):
    self._CheckFunnel(True, target)
    while self.left_funnel:
      self.shortest_path.append(self.left_funnel.popleft())

  def _CheckFunnel(self, left_funnel_first, added_point):
    def Orientation(segment, point):
      # if segment[0] == segment[1]:
      #   return 1 if segment[0] == point else 4
      area = np.cross(segment[0].xy - point.xy, segment[1].xy - point.xy)
      return 3 if area < -_EPSILON else 2 if area > _EPSILON else 1

    first_funnel = self.right_funnel
    second_funnel = self.left_funnel
    if left_funnel_first:
      first_funnel = self.left_funnel
      second_funnel = self.right_funnel
    if len(first_funnel) + len(second_funnel) <= 3:
      if len(first_funnel) == 1:
        first_funnel.append(added_point)
      else:
        first_funnel.pop()
        first_funnel.append(added_point)
      return
    before = None
    after = None
    sweep_line = (added_point, first_funnel[-1])
    temp_point = first_funnel[-1]
    first_funnel.pop()
    after = first_funnel[-1]
    if left_funnel_first:
      if Orientation(sweep_line, after) == 3 or Orientation(sweep_line, after) == 1:
        self.left_funnel.append(temp_point)
        self.left_funnel.append(added_point)
        return
    elif Orientation(sweep_line, after) == 2 or Orientation(sweep_line, after) == 1:
      self.right_funnel.append(temp_point)
      self.right_funnel.append(added_point)
      return
    first_funnel.append(temp_point)
    while len(first_funnel) > 1:
      if len(first_funnel) == 2:
        sweep_line = (added_point, first_funnel[0])
        temp_point = first_funnel[0]
        first_funnel.popleft()
        before = first_funnel[0]
        second_temp_point = second_funnel[0]
        second_funnel.popleft()
        if Orientation(sweep_line, before) != Orientation(sweep_line, second_funnel[0]):
          first_funnel.pop()
          first_funnel.append(added_point)
          first_funnel.appendleft(temp_point)
          second_funnel.appendleft(second_temp_point)
          return
        first_funnel.appendleft(temp_point)
        second_funnel.appendleft(second_temp_point)
        first_funnel.clear()
        break
      before = first_funnel[-1]
      first_funnel.pop()
      sweep_line = (added_point, first_funnel[-1])
      temp_point = first_funnel[-1]
      first_funnel.pop()
      after = first_funnel[-1]
      if Orientation(sweep_line, before) == Orientation(sweep_line, after):
        first_funnel.append(temp_point)
        first_funnel.append(added_point)
        return
      if Orientation(sweep_line, after) == 1:
        first_funnel.append(temp_point)
        first_funnel.append(added_point)
        return
      first_funnel.append(temp_point)
    while len(second_funnel) > 1:
      before = second_funnel[0]
      second_funnel.popleft()
      sweep_line = (added_point, second_funnel[0])
      if len(second_funnel) == 1:
        self.shortest_path.append(before)
        first_funnel.append(second_funnel[0])
        first_funnel.append(added_point)
        return
      temp_point = second_funnel[0]
      second_funnel.popleft()
      after = second_funnel[0]
      if Orientation(sweep_line, before) == Orientation(sweep_line, after):
        self.shortest_path.append(before)
        second_funnel.appendleft(temp_point)
        first_funnel.append(temp_point)
        first_funnel.append(added_point)
        return
      self.shortest_path.append(before)
      second_funnel.appendleft(temp_point)


################################################################
# Build corridor helper function for shortest path computation #
################################################################

def _BuildEdge(start_triangle_index, end_triangle_index, simplices, points):
  # Find points in common.
  common_point_indices = list(set(simplices[start_triangle_index]) & set(simplices[end_triangle_index]))
  assert len(common_point_indices) == 2, 'Ooops'  # There must be two.
  # Find which point is on the left or the right side of the connection edge.
  start_center = np.mean(points[simplices[start_triangle_index]], axis=0)
  end_center = np.mean(points[simplices[end_triangle_index]], axis=0)
  center_to_center = end_center - start_center
  center_to_common = points[common_point_indices[0]] - start_center
  if np.cross(center_to_center, center_to_common) > 0.:
    # Then first common point is on the left side.
    return Edge(Point(start_triangle_index, start_center),
                Point(end_triangle_index, end_center),
                Gate(Point(common_point_indices[0], points[common_point_indices[0]]),
                     Point(common_point_indices[1], points[common_point_indices[1]])))
  return Edge(Point(start_triangle_index, start_center),
              Point(end_triangle_index, end_center),
              Gate(Point(common_point_indices[1], points[common_point_indices[1]]),
                   Point(common_point_indices[0], points[common_point_indices[0]])))


#################
# Build polygon #
#################

def _FindIntersectionIndex(coords, segment):
  for i, pa in enumerate(coords):
    pb = coords[i + 1] if i < len(coords) else coords[0]
    line_segment = geometry.LineString([pa, pb])
    intersection = line_segment.intersection(segment)
    # There must be a single intersection point.
    if not isinstance(intersection, geometry.Point):
      continue
    return intersection.coords[0], i + 1
  return None, None


def _CutLineRing(line_ring, segment, offset):
  coords = list(line_ring.coords)
  start_xy, start_index = _FindIntersectionIndex(coords, segment)
  if start_xy is None:
    raise ValueError('Wrongly created circuit: the starting line must cross both road limit once and only once.')
  # Build cut line ring.
  points = [start_xy]
  factor = None
  for i in range(len(coords)):
    point = coords[(start_index + i) % len(coords)]
    if start_xy == point:
      continue
    if factor is None:
      dp = np.array((point[0] - start_xy[0], point[1] - start_xy[1]))
      if dp.dot(offset) > 0:
        factor = _OFFSET_FACTOR
      else:
        factor = -_OFFSET_FACTOR
    points.append(point)
  points.append((start_xy[0] - 2. * factor * offset[0], start_xy[1] - 2. * factor * offset[1]))
  points[0] = (start_xy[0] - factor * offset[0], start_xy[1] - factor * offset[1])
  g = geometry.LineString(points)
  if not line_ring.is_ccw:
    g.coords = reversed(list(g.coords))
  return g
