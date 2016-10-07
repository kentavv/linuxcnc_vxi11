#!/usr/bin/python

# Goal: Use LinuxCNC to move a probe in a rectilinear grid pattern and take measurements at each point

# Precondition: Before running this program, configure LinuxCNC, home axes, touch off probe, configure
# desired units, etc. Failure to do this could lead to damage.

# Written October 2, 2016 by Kent A. Vander Velden <kent.vandervelden@gmail.com>
#
# To the extent possible under law, the author(s) have dedicated all copyright 
# and related and neighboring rights to this software to the public domain 
# worldwide. This software is distributed without any warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication along 
# with this software. If not, see 
#                       <http://creativecommons.org/publicdomain/zero/1.0/>. 
#
#
# If you use this software, please consider contacting me. I'd like to hear
# about your work.


# Documentation for external libraries
# http://linuxcnc.org/docs/2.6/html/common/python-interface.html
# http://linuxcnc.org/docs/2.7/html/config/python-interface.html
# https://github.com/python-ivi/python-vxi11


import sys
import time
import datetime

import linuxcnc
import vxi11


if len(sys.argv) != 1 + 3*3:
  print 'usage: {0:s} <xs> <xe> <xd>  <ys> <ye> <yd>  <zs> <ze> <zd>'.format(sys.argv[0])
  sys.exit(1)

args = map(float, sys.argv[1:])



cnc_s = linuxcnc.stat()
cnc_c = linuxcnc.command()


# to calculate homed, we iterate over the axes, finding those that are present on this machine,
# and logically combining their homed state (for LinuxCNC 2.7)
def ok_for_mdi27():
  cnc_s.poll()
  homed = True
  for axis in cnc_s.axis:
    homed = homed and ((not axis['enabled']) or (axis['homed'] != 0))
  return not cnc_s.estop and cnc_s.enabled and homed and (cnc_s.interp_state == linuxcnc.INTERP_IDLE)

def verify_ok_for_mdi():
  if not ok_for_mdi27():
    print 'Not ready for MDI commands'
    sys.exit(1)

verify_ok_for_mdi()

cnc_c.mode(linuxcnc.MODE_MDI)
cnc_c.wait_complete()

def move_to(x, y, z):
  cmd = 'G1 G54 X{0:f} Y{1:f} Z{2:f} f5'.format(x, y, z)
  print 'Command,' + cmd
  verify_ok_for_mdi()

  cnc_c.mdi(cmd)
  rv = cnc_c.wait_complete(60)
  if rv != 1:
    print 'MDI command timed out'
    sys.exit(1)



instr = vxi11.Instrument('192.168.0.38')
idn = instr.ask('*IDN?')
if not idn.startswith('Agilent Technologies,34461A'):
  print 'Unknown instrument:', idn
  sys.exit(1)
instr.write('*RST')
instr.write('CONF:VOLT:DC AUTO,DEF')

# read three values with a small delay between each reading
def sample():
  rv = []
  for i in range(3):
    rv += [instr.ask('READ?')]
    time.sleep(.05)
  rv = map(float, rv)
  return rv



# generate grid points in a zig-zag rectalinear pattern, helper function
# s: vector of start positions for each axis
# d: vector of step size for each axis
# n: vector of number of steps for each axis
# o: vector of 1,-1 controlling direction axis is traversed
# l: recursion depth
# p: vector containing current position 
# rv: vector containing accumulated positions
def gen_grid_(s, d, n, o, l, p, rv):
  if l == len(p):
    pp = [x for x in p]
    for i in range(len(pp)):
      pp[i] = s[i] + d[i] * pp[i]
    rv += [pp]
    return

  for i in range(n[l]):
    gen_grid_(s, d, n, o, l+1, p, rv)
    p[l] += o[l]

  if o[l] == 1:
    o[l] = -1
    p[l] = n[l] - 1
  elif o[l] == -1:
    o[l] = 1
    p[l] = 0

# generate grid points in a zig-zag rectalinear pattern
# s: vector of start positions for each axis
# e: vector of end positions for each axis
# d: vector of step size for each axis
# returns: vector containing ordered grid positions
def gen_grid(s, e, d):
  n = [1] * len(s)
  for i in range(len(n)):
    n[i] = int((e[i] - s[i]) / d[i] + 1.5)

  grid_pts = []
  gen_grid_(s[::-1], d[::-1], n[::-1], [1]*len(s), 0, [0]*len(s), grid_pts)
  return grid_pts

s = args[0::3]
e = args[1::3]
d = args[2::3]

grid_pts = gen_grid(s, e, d)
for pp in grid_pts:
  z, y, x = pp
  move_to(x, y, z)
  time.sleep(.1) # settling time
  rv = sample()
  dt = str(datetime.datetime.now())
  print 'Result,' + ','.join(map(str, [dt, x, y, z] + rv))
  sys.stdout.flush()
