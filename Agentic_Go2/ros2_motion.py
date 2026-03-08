
# ros_motion.py
import threading
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import Twist
from std_msgs.msg import String

class _CmdVelNode(Node):
    def __init__(self, topic: str = "/cmd_vel"):
        super().__init__("cmdvel_node")
        self.pub = self.create_publisher(Twist, topic, 10)
        self.tts_pub = self.create_publisher(String, "/tts", 10)

    def publish_twist(self, linear_x: float, angular_z: float = 0.0):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.pub.publish(msg)

    def publish_tts(self, text: str): 
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)

class RosMotionController:
    """
    Keeps ROS2 running in a background thread, and provides simple motion methods.
    """

    def __init__(self, cmd_vel_topic: str = "/cmd_vel"):
        self._topic = cmd_vel_topic
        self._executor: Optional[SingleThreadedExecutor] = None
        self._node: Optional[_CmdVelNode] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._started = False

    def start(self):
        """Initialize rclpy and start spinning in a background thread."""
        if self._started:
            return

        rclpy.init(args=None)
        self._node = _CmdVelNode(topic=self._topic)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        def _spin():
            try:
                self._executor.spin()
            finally:
                # executor.spin exits only when shutdown or error
                pass

        self._spin_thread = threading.Thread(target=_spin, daemon=True)
        self._spin_thread.start()
        self._started = True

    def stop(self):
        """Stop motion, shutdown ROS2."""
        if not self._started:
            return
        self.publish_stop()

        # shutdown executor/node
        if self._executor and self._node:
            self._executor.remove_node(self._node)
            self._node.destroy_node()

        rclpy.shutdown()
        self._started = False

    def publish_stop(self):
        """Publish a zero-velocity command once."""
        if not self._node:
            raise RuntimeError("RosMotionController not started. Call start() first.")
        self._node.publish_twist(0.0, 0.0)

    def walk(self, duration_s: float = 1.0, speed_mps: float = 0.3, rate_hz: float = 10.0):
        """
        Publish forward cmd_vel for duration, then publish stop.
        """
        if not self._node:
            raise RuntimeError("RosMotionController not started. Call start() first.")

        dt = 1.0 / float(rate_hz)
        t_end = time.time() + float(duration_s)

        while time.time() < t_end:
            self._node.publish_twist(speed_mps, 0.0)
            time.sleep(dt)

        self.publish_stop()

    def turn_in_place(
        self,
        duration_s: float = 1.0,
        angular_z: float = 0.8,
        rate_hz: float = 10.0,
    ):
        """
        Publish an in-place rotation cmd_vel for duration, then publish stop.
        Positive angular_z = CCW, negative = CW (ROS standard).
        Blocking, same style as walk_forward().
        """
        if not self._node:
            raise RuntimeError("RosMotionController not started. Call start() first.")

        dt = 1.0 / float(rate_hz)
        t_end = time.time() + float(duration_s)

        while time.time() < t_end:
            # turn in place: linear_x = 0, angular_z != 0
            self._node.publish_twist(0.0, angular_z)
            time.sleep(dt)

        self.publish_stop()

    def say(self, text: str):
        """Publish text to /tts for the robot to speak."""
        if not self._node:
            raise RuntimeError("RosMotionController not started. Call start() first.")
        self._node.publish_tts(text)
