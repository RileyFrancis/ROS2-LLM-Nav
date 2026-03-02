### Some useful commands:

Starting the robot:
- `cd Documents/Code/go2_ros2_sdk/docker/`
- `xhost +local:docker`
- `ROBOT_IP=192.168.50.150 CONN_TYPE=webrtc docker compose up`
- `docker exec -it docker-unitree_ros-1 bash`
- `OLLAMA_HOST=0.0.0.0 ollama serve`

Publish a movement request to the robot:
- `ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: -0.5}, angular: {z: 0.0}}"`

Start llm-nav (Each must be done in a separate terminal):
- `ros2 run object_detection detector_node` (Start object detection)
- `ros2 run object_navigation navigation_node` (Start object nav)
- `ros2 topic pub /navigate_to_object std_msgs/String "data: 'chair_1'"` (Publish a movement request)
- `ros2 topic echo /detected_objects_dict` (View object dictionary)

### go2_ros2_sdk
This repository makes use of the code from [go2_ros2_sdk code repository](https://github.com/abizovnuralem/go2_ros2_sdk)
