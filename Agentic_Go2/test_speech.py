#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time

class SpeakNode(Node):
    def __init__(self):
        super().__init__("speak_node")
        self.pub = self.create_publisher(String, "/tts", 10)

    def say(self, text: str):
        # Wait for tts_node to be ready
        time.sleep(1.0)
        msg = String()
        msg.data = text
        self.pub.publish(msg)
        self.get_logger().info(f"Published: {text}")

def main():
    rclpy.init()
    node = SpeakNode()
    node.say("Hello, I am Go2 HAHAHA")
    
    # Keep alive long enough for message to send
    time.sleep(2.0)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()