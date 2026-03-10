#!/usr/bin/env python3
# test_motion.py

import sys
import time
from ros2_motion import RosMotionController

def print_menu():
    """Print available commands."""
    print("\n" + "="*60)
    print("🤖 ROBOT MOTION CONTROLLER - Interactive Test")
    print("="*60)
    print("\nAvailable Commands:")
    print("\n📍 BASIC MOTION:")
    print("  walk [duration] [speed]     - Walk forward (default: 2s, 0.3 m/s)")
    print("  turn [duration] [speed]     - Turn in place (default: 2s, 0.8 rad/s)")
    print("  stop                        - Stop all motion")
    print("\n🎭 SPORT MODES:")
    print("  sit [duration]              - Sit down (default: 3s)")
    print("  dance [type] [duration]     - Dance type 1 or 2 (default: type 1, 5s)")
    print("  stretch [duration]          - Stretch (default: 3s)")
    print("  wiggle [duration]           - Wiggle hips (default: 3s)")
    print("  stomp [duration]            - Stomp feet (default: 3s)")
    print("  standup                     - Stand up")
    print("  standdown                   - Stand down")
    print("  recover                     - Recovery stand")
    print("\n🗣️  SPEECH:")
    print("  say <text>                  - Speak text via TTS")
    print("\n⚙️  SYSTEM:")
    print("  help                        - Show this menu")
    print("  quit/exit                   - Exit program")
    print("="*60)

def parse_command(controller, cmd_line):
    """Parse and execute a command."""
    parts = cmd_line.strip().split()
    
    if not parts:
        return True
    
    cmd = parts[0].lower()
    
    try:
        # BASIC MOTION
        if cmd == "walk":
            duration = float(parts[1]) if len(parts) > 1 else 2.0
            speed = float(parts[2]) if len(parts) > 2 else 0.3
            print(f"🚶 Walking for {duration}s at {speed} m/s...")
            controller.walk(duration_s=duration, speed_mps=speed)
            print("✅ Walk complete")
            
        elif cmd == "turn":
            duration = float(parts[1]) if len(parts) > 1 else 2.0
            speed = float(parts[2]) if len(parts) > 2 else 0.8
            print(f"🔄 Turning for {duration}s at {speed} rad/s...")
            controller.turn_in_place(duration_s=duration, angular_z=speed)
            print("✅ Turn complete")
            
        elif cmd == "stop":
            print("🛑 Stopping...")
            controller.publish_stop()
            print("✅ Stopped")
            
        # SPORT MODES
        elif cmd == "sit":
            duration = float(parts[1]) if len(parts) > 1 else 3.0
            print(f"🪑 Sitting for {duration}s...")
            controller.sit(duration_s=duration)
            print("✅ Sit complete")
            
        elif cmd == "dance":
            dance_type = int(parts[1]) if len(parts) > 1 else 1
            duration = float(parts[2]) if len(parts) > 2 else 5.0
            if dance_type not in [1, 2]:
                print("❌ Dance type must be 1 or 2")
                return True
            print(f"💃 Dancing (type {dance_type}) for {duration}s...")
            controller.dance(dance_type=dance_type, duration_s=duration)
            print("✅ Dance complete")
            
        elif cmd == "stretch":
            duration = float(parts[1]) if len(parts) > 1 else 3.0
            print(f"🧘 Stretching for {duration}s...")
            controller.stretch(duration_s=duration)
            print("✅ Stretch complete")
            
        elif cmd == "wiggle":
            duration = float(parts[1]) if len(parts) > 1 else 3.0
            print(f"🕺 Wiggling hips for {duration}s...")
            controller.wiggle_hips(duration_s=duration)
            print("✅ Wiggle complete")
            
        elif cmd == "stomp":
            duration = float(parts[1]) if len(parts) > 1 else 3.0
            print(f"👟 Stomping feet for {duration}s...")
            controller.stomp_feet(duration_s=duration)
            print("✅ Stomp complete")
            
        elif cmd == "standup":
            print("⬆️  Standing up...")
            controller.stand_up()
            print("✅ Stand up complete")
            
        elif cmd == "standdown":
            print("⬇️  Standing down...")
            controller.stand_down()
            print("✅ Stand down complete")
            
        elif cmd == "recover":
            print("🔄 Recovery stand...")
            controller.recovery_stand()
            print("✅ Recovery complete")
            
        # SPEECH
        elif cmd == "say":
            if len(parts) < 2:
                print("❌ Usage: say <text>")
                return True
            text = " ".join(parts[1:])
            print(f"🗣️  Saying: '{text}'")
            controller.say(text)
            print("✅ Speech sent")
            
        # SYSTEM
        elif cmd in ["help", "h", "?"]:
            print_menu()
            
        elif cmd in ["quit", "exit", "q"]:
            print("\n👋 Exiting...")
            return False
            
        else:
            print(f"❌ Unknown command: '{cmd}'. Type 'help' for available commands.")
            
    except ValueError as e:
        print(f"❌ Invalid parameter: {e}")
    except Exception as e:
        print(f"❌ Error executing command: {e}")
    
    return True

def main():
    """Main interactive loop."""
    print("\n🚀 Starting Robot Motion Controller...")
    
    controller = RosMotionController()
    
    try:
        controller.start()
        print("✅ Controller started successfully!")
        time.sleep(1)  # Give ROS time to initialize
        
        print_menu()
        
        # Interactive command loop
        while True:
            try:
                cmd_line = input("\n🤖 Enter command: ").strip()
                
                if not cmd_line:
                    continue
                
                # Execute command
                should_continue = parse_command(controller, cmd_line)
                
                if not should_continue:
                    break
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Ctrl+C detected. Stopping...")
                break
            except EOFError:
                print("\n\n⚠️  EOF detected. Stopping...")
                break
                
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
    finally:
        print("\n🛑 Shutting down controller...")
        controller.stop()
        print("✅ Shutdown complete. Goodbye!")

if __name__ == "__main__":
    main()