# Agentic Go2

LLM-powered movement agent for the Unitree Go2 robot.

## Scripts

| Script | Description |
|--------|-------------|
| `Agent_move.py` | Single command at a time |
| `Agent_multistep.py` | Plans and executes multiple commands from one request |
| `Agent_multistep_audio.py` | Multi-step with the robot speaking each step aloud as it executes |

## Setup

**1. Start the Docker container**
```bash
cd docker
docker-compose up
```

**2. Create a `.env` file in `Agentic_Go2/`**
```
OPENAI_API_KEY="your-api-key-here"
```

**3. Create a venv and install dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```


## Audio setup (required for `Agent_multistep_audio.py` only)

In a second terminal, attach to the running Docker container and start the TTS node:

```bash
ros2 run speech_processor tts_node --ros-args \
  -p api_key:="your-elevenlabs-key-here" \
  -p provider:="elevenlabs" \
  -p playback:="robot"
```

Test Audio, in a new terminal
```
docker exec -it <docker-container-name> bash 
ros2 topic pub /tts std_msgs/msg/String "{data: 'Hello, I am Go2'}" --once
```


## Running

```bash
python3 Agent_move.py
# or
python3 Agent_multistep.py
# or
python3 Agent_multistep_audio.py
```
