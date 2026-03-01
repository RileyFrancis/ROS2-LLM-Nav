import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String

from cv_bridge import CvBridge
from ultralytics import YOLO
from rclpy.qos import qos_profile_sensor_data

import numpy as np
import json


class ObjectDetector(Node):

    def __init__(self):
        super().__init__("object_detector")

        self.bridge = CvBridge()
        self.model = YOLO("yolov8n.pt")

        # Subscribe to RGB image
        self.rgb_sub = self.create_subscription(
            Image,
            "/camera/image_raw",
            self.rgb_callback,
            qos_profile_sensor_data
        )

        # Annotated image publisher
        self.annotated_pub = self.create_publisher(
            Image,
            "/detections/image_annotated",
            10
        )

        # 2D pose estimate publisher
        self.object_pose_pub = self.create_publisher(
            PoseStamped,
            "/detected_objects",
            10
        )

        # Dictionary publisher
        self.dict_pub = self.create_publisher(
            String,
            "/detected_objects_dict",
            10
        )

        # Object dictionary
        self.object_map = {}

        # Assume 90 degree horizontal field of view
        self.horizontal_fov = np.deg2rad(90)

        self.get_logger().info("RGB-only object detector ready")

    def rgb_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")

        results = self.model(frame)

        # Publish annotated image
        annotated = results[0].plot()
        annotated_msg = self.bridge.cv2_to_imgmsg(annotated, encoding="bgr8")
        self.annotated_pub.publish(annotated_msg)

        image_width = frame.shape[1]
        image_height = frame.shape[0]

        # Clear dictionary each frame
        self.object_map.clear()

        for i, box in enumerate(results[0].boxes):

            cls = int(box.cls[0])
            label = self.model.names[cls]

            x1, y1, x2, y2 = box.xyxy[0]

            center_x = (x1 + x2) / 2
            box_height = (y2 - y1)

            # Normalize horizontal position [-1, 1]
            normalized_x = (center_x - image_width / 2) / (image_width / 2)

            # Convert to angle
            angle = normalized_x * (self.horizontal_fov / 2)

            # Rough distance estimate from bounding box height
            distance_estimate = 1.0 / (box_height / image_height + 1e-6)

            # Convert to robot-frame 2D estimate
            x_pos = float(distance_estimate * np.cos(angle))
            y_pos = float(distance_estimate * np.sin(angle))

            object_id = f"{label}_{i+1}"

            # Store in dictionary
            self.object_map[object_id] = {
                "x": round(x_pos, 2),
                "y": round(y_pos, 2)
            }

            # Publish PoseStamped for RViz
            pose = PoseStamped()
            pose.header.frame_id = "base_link"
            pose.header.stamp = self.get_clock().now().to_msg()

            pose.pose.position.x = x_pos
            pose.pose.position.y = y_pos
            pose.pose.position.z = 0.0

            self.object_pose_pub.publish(pose)

        # Publish dictionary as JSON
        json_msg = String()
        json_msg.data = json.dumps(self.object_map)
        self.dict_pub.publish(json_msg)

        # Log dictionary
        if self.object_map:
            self.get_logger().info(f"Objects: {self.object_map}")


def main():
    rclpy.init()
    node = ObjectDetector()
    rclpy.spin(node)
    rclpy.shutdown()