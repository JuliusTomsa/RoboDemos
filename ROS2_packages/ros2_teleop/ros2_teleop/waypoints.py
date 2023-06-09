#!/usr/bin/env python
import sys
import yaml
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.clock import Clock
from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import Joy
from pymoveit2 import MoveIt2Servo
from pymoveit2.robots import panda
from keyboard_msgs.msg import KeyboardState
from sensor_msgs.msg import JointState


def is_zero_twist(Lx, Ly, Lz, Ax, Ay, Az):
    arr = [Lx, Ly, Lz, Ax, Ay, Az]
    for a in arr:
        if abs(a) > 1e-10:
            return False
    return True


class WaypointNode(Node):
    
    def __init__(self):
        
        # Create Teleop Node
        super().__init__("waypoint_node")

        # Declare launch parameter to start joystick controller (works with generic controller in Linux)
        self.declare_parameter("start_joy", True)
        self.start_joy = self.get_parameter("start_joy").get_parameter_value().bool_value

        # Declare launch parameter to load config:
        self.declare_parameter("config_path", "")
        config_path = (
            self.get_parameter("config_path").get_parameter_value().string_value
        )
        # Open config path
        try:
            with open(config_path, "r", encoding="utf-8") as infile:
                self.config = yaml.safe_load(infile)
        except Exception as err:
            sys.exit(0)

        # Create callback group that allows execution of callbacks in parallel without restrictions
        callback_group = ReentrantCallbackGroup()

        # Default speed settings
        self.linear_speed = 2
        self.angular_speed = 4
        self.show_speed_settings() # Print default speed settings
        
        # Create MoveIt2 Servo
        self.moveit2_servo = MoveIt2Servo(
            node=self,
            frame_id=panda.base_link_name(),
            callback_group=callback_group,
        )

        if self.start_joy:
            # Create /joy subsriber
            self.subscription = self.create_subscription(
                Joy, "/joy", self.joy_listener_callback, 10
            )
            self.subscription  # prevent unused variable warning

        # Create /keyboard_msgs subsriber
        self.subscription = self.create_subscription(
            KeyboardState, "/keyboard_msgs", self.keyboard_listener_callback, 10
        )
        self.subscription  # prevent unused variable warning
        
        # Create /joint_state subsriber
        self.subscription = self.create_subscription(
            JointState, "/joint_states", self.joint_listener_callback, 10
        )
        self.subscription  # prevent unused variable warning
        
        # Last message initialization
        self.last_joint = JointState()
        self.last_keyboard = KeyboardState()
        self.last_joystick = Joy()

        # Saving waypoints and traces
        self.waypoint_count = 0
        self.save_waypoint = False
        self.last_waypoint_time = None
        self.traces_count = 0
        self.save_traces = False
        self.saving_traces_enabled = False
        self.last_traces_time = None
        self.table_header = None
        self.waypoints_path = self.config["waypoints_dir"] # edit config file to change
        self.traces_path_tmpl = self.config["traces_dir_tmpl"] # edit config file to change

    # Function for displaying current speed settings
    def show_speed_settings(self):
        self.get_logger().info(
            f"\nLinear speed: {round(self.linear_speed, 3)} \nAngular speed: {round(self.angular_speed, 3)}"
        )
    
    # Callback functions:

    def joint_listener_callback(self, msg):
        self.last_joint = msg

    def joy_listener_callback(self, msg):
        self.last_joystick = msg
        self.update_command()

    def keyboard_listener_callback(self, msg):
        self.last_keyboard = msg         
        self.update_command()

    # Function writing header to CSV files
    def ensure_header(self, msg):
        if self.table_header is None:
            names = msg.name
            self.table_header = list(sorted([n for n in names if "finger" not in n]))
        return ["time_ns"] + self.table_header

    # Function for saving waypoint to CSV
    def waypoint(self):
        msg = self.last_joint
        names = msg.name
        positions = msg.position

        # a single data point
        data = dict(zip(names, positions))
        header = self.ensure_header(msg)

        #Check if file exists
        existed = Path(self.waypoints_path).exists()
        with open(self.waypoints_path, "a", encoding="utf-8") as outfile:
            if not existed: 
                # file is new, write header!
                outfile.write(",".join(header) + "\n")
            
            time_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)

            datarow = [time_ns] + [data[n] for n in header[1:]]
            outfile.write(",".join([str(d) for d in datarow]) + "\n")
        
        self.get_logger().info(f"Waypoint{self.waypoint_count} Saved!")
        self.waypoint_count += 1
        self.save_waypoint = False

    # Function for saving traces to CSV
    def traces(self):
        msg = self.last_joint
        names = msg.name
        positions = msg.position

        # a single data point
        data = dict(zip(names, positions))
        header = self.ensure_header(msg)
        current_trace = str.format(self.traces_path_tmpl, number=self.traces_count)

        existed = Path(current_trace).exists()
        with open(current_trace, "a", encoding="utf-8") as outfile:
            if not existed: 
                # file is new, write header!
                outfile.write(",".join(header) + "\n")
            
            time_ns = int(msg.header.stamp.sec * 1e9 + msg.header.stamp.nanosec)

            datarow = [time_ns] + [data[n] for n in header[1:]]
            outfile.write(",".join([str(d) for d in datarow]) + "\n")

        self.get_logger().info(f"Recording Traces{self.traces_count}. Press C or L1 to Stop.")

    # Function for toggling saving traces
    def traces_toggle(self):
        self.saving_traces_enabled = not self.saving_traces_enabled
        self.save_traces = False
        if not self.saving_traces_enabled:
            self.get_logger().info(f"Recording Traces{self.traces_count} Stoped")
            self.traces_count += 1

    # Function sending twist command
    def send_twist(self, Lx, Ly, Lz, Ax, Ay, Az):
        twist_msg = TwistStamped()
        twist = twist_msg.twist
        twist_msg.header.stamp = self.get_clock().now().to_msg()
        twist_msg.header.frame_id = "panda_link0"
        twist.linear.x = float(Lx)
        twist.linear.y = float(Ly)
        twist.linear.z = float(Lz)
        twist.angular.x = float(Ax)
        twist.angular.y = float(Ay)
        twist.angular.z = float(Az)
        self.moveit2_servo(
            linear=(twist.linear.x, twist.linear.y, twist.linear.z),
            angular=(twist.angular.x, twist.angular.y, twist.angular.z),
        )

    # Function returning twist vector calculated from keyboard inputs
    def keyboard_update(self):
            
        k = self.last_keyboard
        
        # Speed settings
        coefficients = [0.9, 1.1]

        # Keyboard speed settings
        # Linear speed
        if k.key_r:
            self.linear_speed *= coefficients[1]
            self.show_speed_settings()
        elif k.key_f:
            self.linear_speed *= coefficients[0]
            self.show_speed_settings()
        # Angular speed
        if k.key_y:
            self.angular_speed *= coefficients[1]
            self.show_speed_settings()
        elif k.key_h:
            self.angular_speed *= coefficients[0]
            self.show_speed_settings()

        # Initialize twist linear and angular values
        Lx = 0
        Ly = 0
        Lz = 0
        Ax = 0
        Ay = 0
        Az = 0

        # X Axis
        if k.key_w:
            Lx = 1 * self.linear_speed
        elif k.key_s:
            Lx = -1 * self.linear_speed

        # Y Axis
        if k.key_a:
            Ly = 1 * self.linear_speed
        elif k.key_d:
            Ly = -1 * self.linear_speed

        # Z Axis
        if k.key_q:
            Lz = 1 * self.linear_speed
        elif k.key_e:
            Lz = -1 * self.linear_speed

        # X Axis turn
        if k.key_l:
            Ax = 1 * self.angular_speed
        elif k.key_j:
            Ax = -1 * self.angular_speed

        # Y Axis turn
        if k.key_i:
            Ay = 1 * self.angular_speed
        elif k.key_k:
            Ay = -1 * self.angular_speed

        # Z Axis turn
        if k.key_u:
            Az = 1 * self.angular_speed
        elif k.key_o:
            Az = -1 * self.angular_speed

        # Waypoint Saving binding
        if k.key_n:

            current_time_waypoint = self.get_clock().now()
            
            if self.last_waypoint_time is None or (self.last_waypoint_time is not None and (current_time_waypoint - self.last_waypoint_time).nanoseconds >= 1e9):
                self.last_waypoint_time = current_time_waypoint
                self.save_waypoint = True

        
        # Traces Saving Enable/Disable binding
        if k.key_c:
            
            current_time_traces = self.get_clock().now()
            
            if self.last_traces_time is None or (self.last_traces_time is not None and (current_time_traces - self.last_traces_time).nanoseconds >= 1e9):
                self.last_traces_time = current_time_traces
                self.save_traces = True

        return Lx, Ly, Lz, Ax, Ay, Az

      
    # Function returning twist vector calculated from joystick inputs
    def joystick_update(self):
        
        j = self.last_joystick

        # Speed settings
        coefficients = [0.9, 1.1]
        
        # Linear speed bindings
        if j.buttons[0]:
            self.linear_speed *= coefficients[0]
            self.show_speed_settings()
        elif j.buttons[3]:
            self.linear_speed *= coefficients[1]
            self.show_speed_settings()

        # Angular speed bindings
        if j.buttons[2]:
            self.angular_speed *= coefficients[0]
            self.show_speed_settings()
        elif j.buttons[1]:
            self.angular_speed *= coefficients[1]
            self.show_speed_settings()

        # Initialize twist linear and angular values
        Lx = 0
        Ly = 0
        Lz = 0
        Ax = 0
        Ay = 0
        Az = 0

        # Joystick bindings
        # twist.linear
        joy_x = j.axes[4]
        joy_y = j.axes[3]
        joy_z = j.axes[1]

        # twist.angular
        joy_ax = j.axes[6]
        joy_ay = j.axes[7]
        joy_az = j.axes[0]

        # Tolerance settings for joystick bindings
        tolerance = 0.0
        # X Axis
        if abs(joy_x) >= tolerance:
            Lx = joy_x * self.linear_speed
        # Y Axis
        if abs(joy_y) >= tolerance:
            Ly = joy_y * self.linear_speed
        # Z Axis
        if abs(joy_z) >= tolerance:
            Lz = joy_z * self.linear_speed
        # Z Axis turn
        if abs(joy_az) >= tolerance:
            Az = joy_az * self.angular_speed

        # Controler button settings
        # Z Axis turn
        Ax = -joy_ax * self.angular_speed
        # Y Axis turn
        Ay = joy_ay * self.angular_speed

        # Waypoint Saving binding
        if j.buttons[5]:

            current_time_waypoint = self.get_clock().now() 

            if self.last_waypoint_time is None or (self.last_waypoint_time is not None and (current_time_waypoint - self.last_waypoint_time).nanoseconds >= 1e9):
                self.last_waypoint_time = current_time_waypoint
                self.save_waypoint = True
        
        # Traces Saving Enable/Disable binding
        if j.buttons[4]:

            current_time_traces = self.get_clock().now()
            
            if self.last_traces_time is None or (self.last_traces_time is not None and (current_time_traces - self.last_traces_time).nanoseconds >= 1e9):
                self.last_traces_time = current_time_traces
                self.save_traces = True

        return Lx, Ly, Lz, Ax, Ay, Az
    
    def update_command(self):            
        
        # Check Joystick for parameters
        try:
            twist_params = self.joystick_update()
            
            # If there is no input from Joystick take input from Keyboard
            if is_zero_twist(*twist_params):
                twist_params =  self.keyboard_update()
        
        # This is used when Joy is not launched
        except:
            twist_params = self.keyboard_update()
              
        # If some input was recorded, send the twist command
        if not is_zero_twist(*twist_params):
            self.send_twist(*twist_params)
        
        # Saving Waypoint
        if self.save_waypoint:
            self.waypoint()
        
        # Enable saving traces (toggle)
        if self.save_traces:
            self.traces_toggle()
                       
        # Save traces
        if self.saving_traces_enabled:
            self.traces()



                 

def main():
    rclpy.init()
    node = WaypointNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()