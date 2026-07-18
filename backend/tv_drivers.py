import os
import sys
import subprocess
import requests
import asyncio
import json
import socket
from backend.config import config

# Handle PyAutoGUI importing issues in headless / linux environments
try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

try:
    import serial
except Exception:
    serial = None

try:
    import websockets
except Exception:
    websockets = None


class BaseTVController:
    """Base class for TV Controllers."""
    def send_command(self, command_name: str) -> bool:
        raise NotImplementedError("Subclasses must implement send_command.")


class LocalPCController(BaseTVController):
    """
    Controls local PC media functions. 
    Useful for testing gesture controls without dedicated TV hardware.
    """
    def __init__(self):
        self.cmd_map = {
            "Power On/Off": "browserhome",
            "Volume Up": "volumeup",
            "Volume Down": "volumedown",
            "Mute": "volumemute",
            "Channel Up": "pageup",
            "Channel Down": "pagedown",
            "Play": "playpause",
            "Pause": "playpause",
            "Play/Pause": "playpause",
            "Home": "browserhome",
            "Back": "esc",
            "Menu": "win",
            "Fast Forward": "fwd",
            "Rewind": "rewind",
            "Next": "nexttrack",
            "Previous": "prevtrack",
            "Launch YouTube": "browserhome",
            "Launch Netflix": "browserhome",
            "Launch Prime Video": "browserhome"
        }

    def send_command(self, command_name: str) -> bool:
        # Map command names to keyboard library hotkey names
        keyboard_map = {
            "Volume Up": "volume up",
            "Volume Down": "volume down",
            "Mute": "volume mute",
            "Play/Pause": "play/pause media",
            "Play": "play/pause media",
            "Pause": "play/pause media",
            "Next": "next track",
            "Previous": "previous track",
            "Power On/Off": "browser home",
            "Home": "browser home",
            "Fast Forward": "right",
            "Rewind": "left"
        }
        
        # 1. Try sending via keyboard module first (more reliable on Windows/Mac)
        k_key = keyboard_map.get(command_name)
        if k_key:
            try:
                import keyboard
                keyboard.send(k_key)
                print(f"[LocalPC] Keyboard module successfully triggered: '{k_key}'")
                return True
            except Exception as ke:
                print(f"[LocalPC] Keyboard module error, falling back: {ke}")
                
        # 2. Fallback to PyAutoGUI press simulation
        if pyautogui is None:
            print(f"[LocalPC] Cannot execute '{command_name}': PyAutoGUI not available.")
            return False
            
        key = self.cmd_map.get(command_name)
        if key:
            try:
                if command_name.startswith("Launch"):
                    print(f"[LocalPC] Mock opening app: '{command_name}'")
                    return True
                pyautogui.press(key)
                print(f"[LocalPC] Simulated keypress: '{key}' for command: '{command_name}'")
                return True
            except Exception as e:
                print(f"[LocalPC] Error pressing key '{key}': {e}")
                return False
        print(f"[LocalPC] Command '{command_name}' not mapped.")
        return False


class WifiTVController(BaseTVController):
    """
    Controls Smart TVs over Wi-Fi. Supports:
    1. Roku TV (External Control Protocol)
    2. Android/Google/Fire TV (via ADB connection)
    3. LG webOS TVs (via WebSockets SSAP protocol)
    4. Samsung Smart TVs (via WebSocket remote key protocol)
    """
    def __init__(self):
        pass

    def send_command(self, command_name: str) -> bool:
        tv_ip = config.get("wifi_tv_ip")
        tv_type = config.get("wifi_tv_type")
        
        # Dispatch to correct smart TV module
        if tv_type == "Roku":
            return self._send_roku(tv_ip, command_name)
        elif tv_type == "AndroidTV" or tv_type == "FireTV" or tv_type == "GoogleTV":
            return self._send_adb_android(tv_ip, command_name)
        elif tv_type == "LGWebOS":
            return asyncio.run(self._send_lg_webos(tv_ip, command_name))
        elif tv_type == "SamsungTizen":
            return asyncio.run(self._send_samsung_tizen(tv_ip, command_name))
        else:
            print(f"[Wi-Fi TV] Unsupported TV type: '{tv_type}'")
            return False

    def _send_roku(self, ip: str, command_name: str) -> bool:
        roku_map = {
            "Power On/Off": "Power",
            "Volume Up": "VolumeUp",
            "Volume Down": "VolumeDown",
            "Mute": "Mute",
            "Channel Up": "ChannelUp",
            "Channel Down": "ChannelDown",
            "Play": "Play",
            "Pause": "Pause",
            "Play/Pause": "Play",
            "Home": "Home",
            "Back": "Back",
            "Menu": "Info",
            "Fast Forward": "Fwd",
            "Rewind": "Rev",
            "Next": "Fwd",
            "Previous": "Rev",
            "Launch YouTube": "launch/837",     # App ID for YouTube on Roku
            "Launch Netflix": "launch/12",      # App ID for Netflix on Roku
            "Launch Prime Video": "launch/13"   # App ID for Prime Video on Roku
        }
        
        key = roku_map.get(command_name)
        if not key:
            print(f"[Roku TV] Command '{command_name}' not supported.")
            return False
            
        # Roku apps launch via different path than keypress
        is_launch = key.startswith("launch/")
        url = f"http://{ip}:8060/{key}" if is_launch else f"http://{ip}:8060/keypress/{key}"
        
        try:
            response = requests.post(url, timeout=2.0)
            if response.status_code == 200:
                print(f"[Roku TV] Successfully sent command: '{key}' to {ip}")
                return True
            else:
                print(f"[Roku TV] Failed to send command, code: {response.status_code}")
                return False
        except Exception as e:
            print(f"[Roku TV] Connection error to {ip}: {e}")
            return False

    def _send_adb_android(self, ip: str, command_name: str) -> bool:
        adb_map = {
            "Power On/Off": "26",
            "Volume Up": "24",
            "Volume Down": "25",
            "Mute": "164",
            "Channel Up": "166",
            "Channel Down": "167",
            "Play": "126",
            "Pause": "127",
            "Play/Pause": "85",
            "Home": "3",
            "Back": "4",
            "Menu": "82",
            "Fast Forward": "90",
            "Rewind": "89",
            "Next": "87",
            "Previous": "88",
        }
        
        # Connect to ADB device
        try:
            subprocess.run(["adb", "connect", f"{ip}:5555"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
        except Exception:
            print("[Android TV] ADB utility not found in path.")
            return False

        # App Launchers (Requires starting intents)
        if command_name.startswith("Launch"):
            intent_map = {
                "Launch YouTube": ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "vnd.youtube://"],
                "Launch Netflix": ["shell", "am", "start", "-n", "com.netflix.ninja/.MainActivity"],
                "Launch Prime Video": ["shell", "am", "start", "-n", "com.amazon.amazonvideo.livingroom/com.amazon.ignite.multiscreen.TargetActivity"]
            }
            cmd = intent_map.get(command_name)
        else:
            keycode = adb_map.get(command_name)
            cmd = ["shell", "input", "keyevent", keycode] if keycode else None
            
        if not cmd:
            print(f"[Android TV] Command '{command_name}' not mapped.")
            return False
            
        try:
            result = subprocess.run(["adb", "-s", f"{ip}:5555"] + cmd, 
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2.0)
            if result.returncode == 0:
                print(f"[Android TV] ADB Command '{command_name}' successfully executed on {ip}")
                return True
            else:
                print(f"[Android TV] ADB Execution failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"[Android TV] Error executing ADB payload: {e}")
            return False

    async def _send_lg_webos(self, ip: str, command_name: str) -> bool:
        if websockets is None:
            print("[LG webOS] Websockets library not available.")
            return False
            
        # SSAP endpoint requests mapping
        lg_map = {
            "Power On/Off": ("ssap://system/turnOff", None),
            "Volume Up": ("ssap://audio/volumeUp", None),
            "Volume Down": ("ssap://audio/volumeDown", None),
            "Mute": ("ssap://audio/setMute", {"mute": True}), # Simply toggle or set true
            "Play": ("ssap://media.controls/play", None),
            "Pause": ("ssap://media.controls/pause", None),
            "Play/Pause": ("ssap://media.controls/play", None),
            "Fast Forward": ("ssap://media.controls/fastForward", None),
            "Rewind": ("ssap://media.controls/rewind", None),
            "Home": ("ssap://system.launcher/open", {"id": "youtube.leanback"}), # Opens YouTube as home representation
            "Launch YouTube": ("ssap://system.launcher/open", {"id": "youtube.leanback"}),
            "Launch Netflix": ("ssap://system.launcher/open", {"id": "netflix"}),
            "Launch Prime Video": ("ssap://system.launcher/open", {"id": "amazon"})
        }
        
        route = lg_map.get(command_name)
        if not route:
            print(f"[LG webOS] Command '{command_name}' not supported.")
            return False
            
        uri, payload = route
        url = f"ws://{ip}:3000"
        
        try:
            async with websockets.connect(url, open_timeout=2.0) as ws:
                # LG Handshake handshake packet registration
                handshake = {
                    "type": "register",
                    "id": "register_0",
                    "payload": {
                        "forcePairing": False,
                        "manifest": {
                            "manifestVersion": 1,
                            "permissions": ["CONTROL_AUDIO", "CONTROL_POWER", "LAUNCH", "CONTROL_INPUT_TEXT"]
                        }
                    }
                }
                await ws.send(json.dumps(handshake))
                # Await handshake reply
                response = await ws.recv()
                
                # Send Command packet
                cmd_packet = {
                    "type": "request",
                    "id": "cmd_1",
                    "uri": uri
                }
                if payload:
                    cmd_packet["payload"] = payload
                    
                await ws.send(json.dumps(cmd_packet))
                print(f"[LG webOS] Successfully wrote WS payload for '{command_name}' to {ip}")
                return True
        except Exception as e:
            print(f"[LG webOS] WebSocket error connecting to {ip}: {e}")
            return False

    async def _send_samsung_tizen(self, ip: str, command_name: str) -> bool:
        if websockets is None:
            print("[Samsung TV] Websockets library not available.")
            return False
            
        samsung_keys = {
            "Power On/Off": "KEY_POWER",
            "Volume Up": "KEY_VOLUP",
            "Volume Down": "KEY_VOLDOWN",
            "Mute": "KEY_MUTE",
            "Channel Up": "KEY_CHUP",
            "Channel Down": "KEY_CHDOWN",
            "Play": "KEY_PLAY",
            "Pause": "KEY_PAUSE",
            "Play/Pause": "KEY_PLAY",
            "Home": "KEY_HOME",
            "Back": "KEY_RETURN",
            "Menu": "KEY_MENU",
            "Fast Forward": "KEY_FF",
            "Rewind": "KEY_REWIND"
        }
        
        key = samsung_keys.get(command_name)
        if not key:
            print(f"[Samsung TV] Command '{command_name}' not supported.")
            return False
            
        url = f"ws://{ip}:8001/api/v2/channels/samsung.remote.control?name=AuraCastController"
        
        try:
            async with websockets.connect(url, open_timeout=2.0) as ws:
                # Send remote control click packet
                payload = {
                    "method": "ms.remote.control",
                    "params": {
                        "Cmd": "Click",
                        "DataOfCmd": key,
                        "Option": "false",
                        "TypeOfRemote": "SendRemoteKey"
                    }
                }
                await ws.send(json.dumps(payload))
                print(f"[Samsung TV] Sent key {key} to {ip}")
                return True
        except Exception as e:
            print(f"[Samsung TV] WebSocket error connecting to {ip}: {e}")
            return False


class IrController(BaseTVController):
    """
    Controls TV via IR.
    - Uses subprocess LIRC (irsend) on Linux/Raspberry Pi.
    - Uses Serial port communication on Windows (connected to Arduino IR blaster).
    """
    def __init__(self):
        self.serial_conn = None

    def _get_serial_connection(self):
        if serial is None:
            print("[IR Controller] PySerial not installed.")
            return None
            
        port = config.get("serial_port")
        baud = config.get("serial_baud")
        
        if self.serial_conn is None or not self.serial_conn.is_open:
            try:
                self.serial_conn = serial.Serial(port, baud, timeout=1.0)
                print(f"[IR Controller] Connected to Arduino IR blaster on {port}")
            except Exception as e:
                print(f"[IR Controller] Serial connection error on {port}: {e}")
                self.serial_conn = None
        return self.serial_conn

    def send_command(self, command_name: str) -> bool:
        if sys.platform.startswith("linux"):
            return self._send_lirc(command_name)
        else:
            return self._send_serial_arduino(command_name)

    def _send_lirc(self, command_name: str) -> bool:
        lirc_map = {
            "Power On/Off": "KEY_POWER",
            "Volume Up": "KEY_VOLUMEUP",
            "Volume Down": "KEY_VOLUMEDOWN",
            "Mute": "KEY_MUTE",
            "Channel Up": "KEY_CHANNELUP",
            "Channel Down": "KEY_CHANNELDOWN",
            "Play": "KEY_PLAY",
            "Pause": "KEY_PAUSE",
            "Play/Pause": "KEY_PLAYPAUSE",
            "Home": "KEY_HOMEPAGE",
            "Back": "KEY_BACK",
            "Menu": "KEY_MENU"
        }
        
        key = lirc_map.get(command_name)
        if not key:
            return False
            
        try:
            subprocess.run(["irsend", "SEND_ONCE", "TV", key], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except Exception as e:
            print(f"[IR LIRC] Failed to send via LIRC: {e}")
            return False

    def _send_serial_arduino(self, command_name: str) -> bool:
        conn = self._get_serial_connection()
        if not conn:
            return False
        try:
            conn.write(f"{command_name}\n".encode("utf-8"))
            return True
        except Exception as e:
            print(f"[IR Serial] Serial write error: {e}")
            self.serial_conn = None
            return False


class HdmiCecController(BaseTVController):
    """Controls TV using HDMI-CEC commands via 'cec-client'."""
    def send_command(self, command_name: str) -> bool:
        cec_map = {
            "Power On/Off": "tx 10 44 40",
            "Volume Up": "tx 10 44 41",
            "Volume Down": "tx 10 44 42",
            "Mute": "tx 10 44 43",
            "Channel Up": "tx 10 44 30",
            "Channel Down": "tx 10 44 31",
            "Play": "tx 10 44 44",
            "Pause": "tx 10 44 46",
            "Play/Pause": "tx 10 44 44",
            "Home": "tx 10 44 09",
            "Back": "tx 10 44 0d"
        }
        
        command = cec_map.get(command_name)
        if not command:
            return False
            
        try:
            p1 = subprocess.Popen(["echo", command], stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["cec-client", "-s", "-d", "1"], stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p1.stdout.close()
            p2.communicate(timeout=3.0)
            return p2.returncode == 0
        except Exception as e:
            print(f"[HDMI-CEC] Error: {e}")
            return False


class BluetoothController(BaseTVController):
    """Controls TV via Bluetooth keyboard simulation."""
    def __init__(self):
        self.local_pc = LocalPCController()

    def send_command(self, command_name: str) -> bool:
        return self.local_pc.send_command(command_name)


# Dispatcher
def execute_tv_command(command_name: str) -> bool:
    """Executes a TV command using the currently configured driver."""
    driver_name = config.get("active_driver", "Local")
    
    if driver_name == "Local":
        controller = LocalPCController()
    elif driver_name == "Wi-Fi":
        controller = WifiTVController()
    elif driver_name == "IR":
        controller = IrController()
    elif driver_name == "Bluetooth":
        controller = BluetoothController()
    elif driver_name == "HDMI-CEC":
        controller = HdmiCecController()
    else:
        controller = LocalPCController()
        
    return controller.send_command(command_name)


# Auto-Detection scanner utility
def scan_network_devices():
    """
    Asynchronously scans ports of local subnet to find potential smart TVs.
    Scans: Roku (8060), LG webOS (3000), Samsung (8001), Android TV (5555)
    Returns: list of dicts with detected devices.
    """
    # Get local IP address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        return []
        
    subnet_prefix = ".".join(local_ip.split(".")[:3])
    detected_devices = []
    
    # Port scan target configuration
    targets = {
        8060: "Roku TV",
        3000: "LG Smart TV (webOS)",
        8001: "Samsung Smart TV",
        5555: "Android TV / ADB"
    }

    # Simple multithreaded socket scan for speed
    def check_host(ip, port, timeout=0.15):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            result = s.connect_ex((ip, port))
            s.close()
            return result == 0
        except Exception:
            return False

    # Scan last octet ranges from 1 to 254
    # To keep GUI responsive, we'll scan in a separate thread. We provide this helper.
    for i in range(1, 255):
        ip = f"{subnet_prefix}.{i}"
        # Skip local IP
        if ip == local_ip:
            continue
        for port, dev_type in targets.items():
            if check_host(ip, port):
                detected_devices.append({"ip": ip, "type": dev_type, "port": port})
                
    return detected_devices
