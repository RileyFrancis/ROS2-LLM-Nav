import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image, PointCloud2, CameraInfo
from nav_msgs.msg import Odometry
from sensor_msgs_py import point_cloud2
from cv_bridge import CvBridge
from rclpy.qos import qos_profile_sensor_data
import message_filters

import std_msgs.msg
import numpy as np


class VLMapNode(Node):

    def __init__(self):
        super().__init__('vlmap_node')

        self.bridge = CvBridge()
        self.rgb = None
        self.pose = None
        self.camera_info = None

        # Get camera intrinsics from camera_info topic
        self.create_subscription(
            CameraInfo,
            '/camera/camera_info',
            self.camera_info_callback,
            qos_profile_sensor_data
        )

        # RGB image subscriber
        self.create_subscription(
            Image,
            '/camera/image_raw',       # ← corrected topic
            self.rgb_callback,
            qos_profile_sensor_data
        )

        # Use the filtered point cloud for depth data
        # Try /pointcloud/filtered first — fall back to /point_cloud2 if empty
        self.create_subscription(
            PointCloud2,
            '/pointcloud/filtered',    # ← LiDAR point cloud instead of depth image
            self.pointcloud_callback,
            qos_profile_sensor_data
        )

        self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        # Publisher
        self.map_pub = self.create_publisher(PointCloud2, "/vlmap/points", 10)

        # Debug timer
        self.create_timer(5.0, self.check_topics)

        self.get_logger().info("VLMap node started")

    def check_topics(self):
        rgb_count   = self.count_publishers('/camera/image_raw')
        cloud_count = self.count_publishers('/pointcloud/filtered')
        odom_count  = self.count_publishers('/odom')
        self.get_logger().info(
            f"Publishers — RGB: {rgb_count}, PointCloud: {cloud_count}, Odom: {odom_count}"
        )

    def camera_info_callback(self, msg):
        if self.camera_info is None:
            self.camera_info = msg
            self.get_logger().info(
                f"Got camera intrinsics: fx={msg.k[0]:.1f}, fy={msg.k[4]:.1f}, "
                f"cx={msg.k[2]:.1f}, cy={msg.k[5]:.1f}"
            )

    def rgb_callback(self, msg):
        self.rgb = self.bridge.imgmsg_to_cv2(msg, "bgr8")

    def odom_callback(self, msg):
        self.pose = msg.pose.pose

    def pointcloud_callback(self, msg):
        """
        The Go2 has no depth camera — use the LiDAR point cloud directly.
        Optionally project RGB colour onto points if they overlap the camera FOV.
        """
        if self.rgb is None:
            return

        # Read XYZ points from the incoming cloud
        raw_points = list(point_cloud2.read_points(
            msg, field_names=("x", "y", "z"), skip_nans=True
        ))

        if len(raw_points) == 0:
            return

        colored_points = []

        if self.camera_info is not None:
            # Project each 3D point into the camera image to sample its colour
            fx = self.camera_info.k[0]
            fy = self.camera_info.k[4]
            cx = self.camera_info.k[2]
            cy = self.camera_info.k[5]
            h, w = self.rgb.shape[:2]

            for x, y, z in raw_points:
                if z <= 0:
                    continue

                # Project into image plane
                u = int(fx * x / z + cx)
                v = int(fy * y / z + cy)

                if 0 <= u < w and 0 <= v < h:
                    b, g, r = self.rgb[v, u]
                    colored_points.append((float(x), float(y), float(z)))
                else:
                    colored_points.append((float(x), float(y), float(z)))
        else:
            colored_points = [(float(x), float(y), float(z)) for x, y, z in raw_points]

        if len(colored_points) == 0:
            return

        header = std_msgs.msg.Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = msg.header.frame_id  # preserve original frame

        cloud = point_cloud2.create_cloud_xyz32(header, colored_points)
        self.map_pub.publish(cloud)
        self.get_logger().info(f"Published {len(colored_points)} points")


def main():
    rclpy.init()
    node = VLMapNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()