from tkinter.ttk import Progressbar
from tqdm import tqdm

'''
This file contains code for outputting a map as an SVG file, without using
mapplotlib.
'''

def draw_mountain(trails, lifts, mountain_name, cardinal_direction):
  '''
  trails: (trail line df, name: string, difficulty modifier: float, area flag: bool, area line df, UNUSED)
  lifts: (lift line df, name: string)
  mountain_name: string
  cardinal_direction: 'n' | 'e' | 's' | 'w'

  Returns string representing svg
  '''

  root = svg_el('svg', {'width': '100%', 'height': '100%', 'xmlns': 'http://www.w3.org/2000/svg', 'xmlns:xlink': "http://www.w3.org/1999/xlink"})

  lat_mirror = 1
  lon_mirror = -1
  flip_lat_lon = False
  if 'e' == cardinal_direction or 'E' == cardinal_direction:
    lat_mirror = -1
    lon_mirror = 1
  if 's' == cardinal_direction or 'S' == cardinal_direction:
    lon_mirror = 1
    flip_lat_lon = True
  if 'n' == cardinal_direction or 'N' == cardinal_direction:
    lat_mirror = -1
    flip_lat_lon = True

  for trail in tqdm(trails, desc="Drawing trails", ascii=False, ncols=75):
    if not flip_lat_lon:
      X = trail[0].lat
      Y = trail[0].lon
    if flip_lat_lon:
      X = trail[0].lon
      Y = trail[0].lat
      lat_mirror, lon_mirror = lon_mirror, lat_mirror

    style = {}
    if not trail[3]:
      if trail[2] == 0:
        style = {'stroke': '#000000', 'stroke-width': '1' }
      else:
        # dashed line
        style = {'stroke': '#000000', 'stroke-width': '1', 'stroke-dasharray': '5,5'}
    else:
      style = {'fill': '#00000088'}
    
    points = []
    for (x, y) in zip(X * lat_mirror, Y * lon_mirror):
      points.append((x, y))
    append_child(root, svg_path(points, style))

  return '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n' + svg_to_string(root)

def svg_to_string(node, indent=0):
  '''
  node: svg node

  Convert an SVG DOM tree to an XML string.
  '''

  output = (' ' * indent) + '<{} {}'.format(node['name'], ' '.join(['{}="{}"'.format(k, v) for k, v in node['attrs'].items()]))

  if len(node['children']) == 0:
    return output + '/>\n'
  
  output += '>\n'
  for child in node['children']:
    output += svg_to_string(child, indent + 2)
  return output + '</{}>'.format(node['name'])

def svg_el(name, attrs={}, children=None):
  '''
  name: string
  attrs: dict with string keys and attributes
  children: list of svg nodes

  Return an SVG element with the given name and attributes.
  '''

  # Can't set children default to [] because python is bad and makes it the same
  # list for every invocation of svg_el. i mean why tf would it do that.
  if children == None:
    children = []
    
  return {
    'name': name,
    'attrs': attrs,
    'children': children,
  }

def append_child(parent, child):
  '''
  parent: svg el
  child: svg el

  Add a child to a parent node.
  '''
  parent['children'].append(child)

def svg_path(points, style, close=False):
  '''
  points: list of (x, y) tuples
  fill: string color
  stroke: string color
  line_width: float

  Return an SVG path element for the given points and style.
  '''
  if len(points) == 0:
    svg_el('p')

  d = ''
  d += 'M{},{}'.format(points[0][0], points[0][1])
  for point in points[1:]:
    d += 'L{},{}'.format(point[0], point[1])
  if close:
    d += 'Z'

  style['d'] = d
  return svg_el('path', style)
