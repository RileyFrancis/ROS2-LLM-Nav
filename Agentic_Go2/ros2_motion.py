# ros_motion.py
import threading
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from go2_interfaces.msg import WebRtcReq


class _CmdVelNode(Node):
    def __init__(self, topic: str = "/cmd_vel"):
        super().__init__("cmdvel_node")
        self.pub = self.create_publisher(Twist, topic, 10)
        self.tts_pub = self.create_publisher(String, "/tts", 10)
        self.sport_mode_pub = self.create_publisher(WebRtcReq, "/webrtc_req", 10)

    def publish_twist(self, linear_x: float, angular_z: float = 0.0):
        msg = Twist()
        msg.linear.x = float(linear_x)
        msg.angular.z = float(angular_z)
        self.pub.publish(msg)

    def publish_tts(self, text: str):
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)

    def publish_sport_mode(self, api_id: int):
        msg = WebRtcReq()
        msg.api_id = api_id
        msg.parameter = ""
        msg.topic = "rt/api/sport/request"
        msg.priority = 0
        self.sport_mode_pub.publish(msg)


class RosMotionController:
    """
    Keeps ROS2 running in a background thread, and provides simple motion methods.
    """

    # Sport mode API IDs (Unitree Go2 sport API)
    SPORT_STAND_UP       = 1004
    SPORT_STAND_DOWN     = 1005
    SPORT_RECOVERY_STAND = 1006
    SPORT_SIT            = 1009
    SPORT_STRETCH        = 1017

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
                pass

        self._spin_thread = threading.Thread(target=_spin, daemon=True)
        self._spin_thread.start()
        self._started = True

    def stop(self):
        """Stop motion and shutdown ROS2."""
        if not self._started:
            return
        self.publish_stop()

        if self._executor and self._node:
            self._executor.remove_node(self._node)
            self._node.destroy_node()

        rclpy.shutdown()
        self._started = False

    def _check_started(self):
        if not self._node:
            raise RuntimeError("RosMotionController not started. Call start() first.")

    def walk(self, duration_s: float = 1.0, speed_mps: float = 0.3, rate_hz: float = 10.0):
        """Walk forward for a given duration."""
        self._check_started()
        dt = 1.0 / float(rate_hz)
        t_end = time.time() + float(duration_s)
        while time.time() < t_end:
            self._node.publish_twist(speed_mps, 0.0)
            time.sleep(dt)
        self.publish_stop()

    def turn_in_place(self, duration_s: float = 1.0, angular_z: float = 0.8, rate_hz: float = 10.0):
        """
        Rotate in place for a given duration.
        Positive angular_z = CCW, negative = CW.
        """
        self._check_started()
        dt = 1.0 / float(rate_hz)
        t_end = time.time() + float(duration_s)
        while time.time() < t_end:
            self._node.publish_twist(0.0, angular_z)
            time.sleep(dt)
        self.publish_stop()

    def publish_stop(self):
        """Publish a zero-velocity command."""
        self._check_started()
        self._node.publish_twist(0.0, 0.0)

    def stand_up(self):
        """Stand up."""
        self._check_started()
        self._node.publish_sport_mode(self.SPORT_STAND_UP)
        time.sleep(2.0)

    def stand_down(self):
        """Lower into a resting stance."""
        self._check_started()
        self._node.publish_sport_mode(self.SPORT_STAND_DOWN)
        time.sleep(2.0)

    def recovery_stand(self):
        """Recover to normal standing position from any pose."""
        self._check_started()
        self._node.publish_sport_mode(self.SPORT_RECOVERY_STAND)
        time.sleep(2.0)

    def sit(self, duration_s: float = 3.0):
        """Sit down, hold, then recovery stand."""
        self._check_started()
        self._node.publish_sport_mode(self.SPORT_SIT)
        time.sleep(duration_s)
        self._node.publish_sport_mode(self.SPORT_RECOVERY_STAND)
        time.sleep(2.0)

    def stretch(self, duration_s: float = 3.0):
        """Stretch, then recovery stand."""
        self._check_started()
        self._node.publish_sport_mode(self.SPORT_STRETCH)
        time.sleep(duration_s)
        self._node.publish_sport_mode(self.SPORT_RECOVERY_STAND)
        time.sleep(2.0)

    def say(self, text: str):
        """Publish text to /tts for the robot to speak."""
        self._check_started()
        self._node.publish_tts(text)