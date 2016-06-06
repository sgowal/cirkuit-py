from shapely import geometry


class Move(object):

  def __init__(self, point, angle):
    self.point = point
    self.angle = angle
