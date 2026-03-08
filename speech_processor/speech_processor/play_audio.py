#!/usr/bin/env python3
import os
import io
import json
import time
import base64
import math

import rclpy
from rclpy.node import Node
from go2_interfaces.msg import WebRtcReq
from pydub import AudioSegment


AUDIO_TOPIC = "rt/api/audiohub/request"

# Keep these aligned with your repo's tts_node / constants
API_ID_START = 4001
API_ID_END   = 4002
API_ID_CHUNK = 4003


class AudioFilePublisher(Node):
    def __init__(self):
        super().__init__("audio_file_publisher")
        self.pub = self.create_publisher(WebRtcReq, "/webrtc_req", 10)

    def send_req(self, api_id: int, parameter: str):
        msg = WebRtcReq()
        msg.api_id = api_id
        msg.priority = 1
        msg.topic = AUDIO_TOPIC
        msg.parameter = parameter
        self.pub.publish(msg)

    def play_file(self, filepath: str, chunk_size: int = 16 * 1024):
        if not os.path.exists(filepath):
            self.get_logger().error(f"File not found: {filepath}")
            return

        # Convert to WAV (keep WAV header, encode the whole thing)
        audio = AudioSegment.from_file(filepath)
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()

        duration_s = len(audio) / 1000.0

        # Encode entire WAV and split
        b64_encoded = base64.b64encode(wav_bytes).decode("utf-8")
        raw_chunks = [
            b64_encoded[i:i + chunk_size]
            for i in range(0, len(b64_encoded), chunk_size)
        ]
        total_chunks = len(raw_chunks)

        self.get_logger().info(f"Sending {total_chunks} chunks, duration {duration_s:.2f}s")
        time.sleep(0.3)
        self.send_req(API_ID_END, "")
        self.get_logger().info("Done")
        time.sleep(0.3)
        # Send start (empty parameter)
        self.send_req(API_ID_START, "")
        time.sleep(0.3)

        # Send chunks with correct keys, 1-based index
        for i, chunk in enumerate(raw_chunks):
            chunk_param = json.dumps({
                "current_block_index": i + 1,
                "total_block_number": total_chunks,
                "block_content": chunk
            })
            self.send_req(API_ID_CHUNK, chunk_param)

            if (i + 1) % 10 == 0:
                self.get_logger().info(f"Sent {i+1}/{total_chunks} chunks")

            time.sleep(0.15)

        # Wait for playback then send end (empty parameter)
        self.get_logger().info(f"Waiting for playback ({duration_s:.1f}s)...")
        time.sleep(duration_s + 1.0)

        self.send_req(API_ID_END, "")
        time.sleep(0.1)
        self.get_logger().info("Done")
def main():
    rclpy.init()
    node = AudioFilePublisher()

    # change this to your actual cached file path
    filepath = "/ros2_ws/tts_cache/0407e67be67809ccc1ac4a091e58fce7.mp3"

    time.sleep(1.0)  # allow publisher discovery
    node.play_file(filepath)

    time.sleep(1.0)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
