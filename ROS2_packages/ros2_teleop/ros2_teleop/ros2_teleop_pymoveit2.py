#!/usr/bin/env python
import rclpy
import time
from rclpy.qos import (
	QoSDurabilityPolicy,
	QoSHistoryPolicy,
	QoSProfile,
	QoSReliabilityPolicy,
)
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped

from pymoveit2 import MoveIt2Servo
from pymoveit2.robots import panda
from std_srvs.srv import Trigger

import sys, select, termios, tty

settings = termios.tcgetattr(sys.stdin)

class ServoClientNode(Node):

	def __init__(self):
		super().__init__('teleop_twist_keyboard')
		# Create callback group that allows execution of callbacks in parallel without restrictions
		callback_group = ReentrantCallbackGroup()

		# Create MoveIt 2 Servo interface
		self.moveit2_servo = MoveIt2Servo(
			node=self,
			frame_id=panda.base_link_name(),
			callback_group=callback_group,
		)
		print("moveit2 servo initialized")

	def teleop(self):

		speed = 0.5
		turn = 1.0
		x = 0
		y = 0
		z = 0
		th = 0
		status = 0

		try:
			print(msg)
			print(vels(speed,turn))
			while(1):
				key = getKey()
				if key in moveBindings.keys():
					x = moveBindings[key][0]
					y = moveBindings[key][1]
					z = moveBindings[key][2]
					th = moveBindings[key][3]
				elif key in speedBindings.keys():
					speed = speed * speedBindings[key][0]
					turn = turn * speedBindings[key][1]

					print(vels(speed,turn))
					if (status == 14):
						print(msg)
					status = (status + 1) % 15
				else:
					x = 0
					y = 0
					z = 0
					th = 0
					if (key == '\x03'):
						break

				twist_msg = TwistStamped()
				twist = twist_msg.twist
				twist_msg.header.stamp = self.get_clock().now().to_msg()
				twist_msg.header.frame_id = "panda_link0"
				twist.linear.x = x*speed
				twist.linear.y = y*speed
				twist.linear.z = z*speed
				twist.angular.x = 0.0
				twist.angular.y = 0.0
				twist.angular.z = th*turn
				self.moveit2_servo(linear=(twist.linear.x, twist.linear.y, twist.linear.z), angular=(twist.angular.x, twist.angular.y, twist.angular.z))
		except Exception as e:
			print(e)

		finally:
			twist_msg = TwistStamped()
			twist = twist_msg.twist
			twist_msg.header.stamp = self.get_clock().now().to_msg()
			twist_msg.header.frame_id = "panda_link0"
			twist.linear.x = 0.0
			twist.linear.y = 0.0
			twist.linear.z = 0.0
			twist.angular.x = 0.0
			twist.angular.y = 0.0
			twist.angular.z = 0.0
			self.moveit2_servo(linear=(twist.linear.x, twist.linear.y, twist.linear.z), angular=(twist.angular.x, twist.angular.y, twist.angular.z))
			
			termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)


msg = """
Reading from the keyboard  and Publishing to Twist!
---------------------------
Moving around:
   u    i    o
   j    k    l
   m    ,    .

For Holonomic mode (strafing), hold down the shift key:
---------------------------
   U    I    O
   J    K    L
   M    <    >

t : up (+z)
b : down (-z)

anything else : stop

q/z : increase/decrease max speeds by 10%
w/x : increase/decrease only linear speed by 10%
e/c : increase/decrease only angular speed by 10%

CTRL-C to quit
"""

moveBindings = {
		'i':(1,0,0,0),
		'o':(1,0,0,-1),
		'j':(0,0,0,1),
		'l':(0,0,0,-1),
		'u':(1,0,0,1),
		',':(-1,0,0,0),
		'.':(-1,0,0,1),
		'm':(-1,0,0,-1),
		'O':(1,-1,0,0),
		'I':(1,0,0,0),
		'J':(0,1,0,0),
		'L':(0,-1,0,0),
		'U':(1,1,0,0),
		'<':(-1,0,0,0),
		'>':(-1,-1,0,0),
		'M':(-1,1,0,0),
		't':(0,0,1,0),
		'b':(0,0,-1,0),
		   }

speedBindings={
		'q':(1.1,1.1),
		'z':(.9,.9),
		'w':(1.1,1),
		'x':(.9,1),
		'e':(1,1.1),
		'c':(1,.9),
		  }

def getKey():
	tty.setraw(sys.stdin.fileno())
	select.select([sys.stdin], [], [], 0)
	key = sys.stdin.read(1)
	termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
	return key


def vels(speed,turn):
	return "currently:\tspeed %s\tturn %s " % (speed,turn)


def main():	
	rclpy.init()
	client = ServoClientNode()

	
	
	print("starting teleop")
	client.teleop()
	

	
	
	client.destroy_node()
	rclpy.shutdown()


	