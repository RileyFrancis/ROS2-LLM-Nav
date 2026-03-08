import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class WalkForward(Node):

    def __init__(self):
        super().__init__('walk_forward_node')

        # Publisher to velocity topic
        self.publisher_ = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )

        # publish at 10 Hz
        self.timer = self.create_timer(0.1, self.move_forward)

        self.get_logger().info("Walking forward...")

    def move_forward(self):
        msg = Twist()

        # Forward velocity (meters/sec)
        msg.linear.x = 0.3

        # No turning
        msg.angular.z = 0.0

        self.publisher_.publish(msg)


def main(args=None):
    rclpy.init(args=args)

    node = WalkForward()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()