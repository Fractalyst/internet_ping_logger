import os
import platform
import subprocess
import threading
import time
from datetime import datetime
import re
import sys
import argparse
import pystray
from PIL import Image
import time
import win32api
import win32con
import json


def get_script_path():
    return os.path.dirname(__file__)


def get_logs_path():
    return os.path.join(get_script_path(), "logs")


def get_file_name(host):
    return f"log_{host}.txt"


def sec_to_hms(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(int(seconds)))


def log_message(host, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = [timestamp, message]

    log_path = get_logs_path()

    if not os.path.exists(log_path):
        os.mkdir(log_path)

    saveFileLocation = os.path.join(log_path, get_file_name(host))
    with open(saveFileLocation, "a") as f:
        f.write(json.dumps(log_message) + "\n")


def log_status(host, host_status, duration=0):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_message = [timestamp, host_status, sec_to_hms(duration)]

    saveFileLocation = os.path.join(get_logs_path(), get_file_name(host))
    with open(saveFileLocation, "a") as f:
        f.write(json.dumps(log_message) + "\n")


import socket


def do_ping(host):
    try:
        with socket.create_connection((host, 443), timeout=2):
            return "ONLINE"
    except TimeoutError:
        return "TIMEOUT"
    except ConnectionRefusedError:
        return "REFUSED"
    except OSError as e:
        if e.errno in (101, 113):
            return "NO_ROUTE"
        return "NETWORK_ERROR"


def start_ping_loop(icon, host, ignore_seconds, halt_event):
    host_reachable_curr = "ONLINE"
    host_reachable_prev = "ONLINE"
    curr_seconds_in_state = 0
    state_change_time = None

    start = time.perf_counter()

    while True:
        if halt_event.is_set():
            # Log final state and exit immediately
            curr_seconds_in_state = int(time.perf_counter() - start)
            log_status(host, host_reachable_curr, curr_seconds_in_state)
            log_message(host, "Closed logger")
            icon.stop()
            return

        host_reachable_curr = do_ping(host)
        curr_seconds_in_state = int(time.perf_counter() - start)

        icon.title = (
            f"Host: {host}\n{host_reachable_prev} : {sec_to_hms(curr_seconds_in_state)}"
        )

        # If status changed from the logged state
        if host_reachable_curr != host_reachable_prev:
            # First time detecting this change
            if state_change_time is None:
                state_change_time = time.perf_counter()

            # Check if enough time has passed to confirm the change
            time_elapsed = time.perf_counter() - state_change_time
            if time_elapsed >= ignore_seconds:
                curr_seconds_in_state = int(time.perf_counter() - start)
                log_status(host, host_reachable_prev, curr_seconds_in_state)
                host_reachable_prev = host_reachable_curr
                start = time.perf_counter()
                state_change_time = None
        else:
            # Status returned to the logged state, reset the change timer
            state_change_time = None

        time.sleep(1)


class Options:
    OPEN_DIR = "Open Logger Directory"
    OPEN_FILE = "Open Logger File"
    EXIT = "Exit"


def setup_systray_icon(host, ignore_seconds):
    # Load icon
    iconPath = os.path.join(get_script_path(), "globe-svgrepo-com.png")
    if not os.path.exists(iconPath):
        log_message(host, "Error: Icon file not found")
        sys.exit()

    image = Image.open(iconPath)

    # Setup state and callbacks
    halt_event = threading.Event()
    logFilePath = os.path.join(get_logs_path(), get_file_name(host))
    log_message(host, f"Starting logger, ignoring {ignore_seconds}s")

    def after_click(icon, query):
        query_str = str(query)
        match query_str:
            case Options.OPEN_DIR:
                os.startfile(get_script_path())
            case Options.OPEN_FILE:
                if not os.path.exists(logFilePath):
                    log_message(host, "Error: Log file not found")
                    sys.exit()
                os.startfile(logFilePath)
            case Options.EXIT:
                halt_event.set()

    # Create icon with menu
    icon = pystray.Icon(
        "InternetPingLogger",
        image,
        "Booting InternetPingLogger",
        menu=pystray.Menu(
            pystray.MenuItem(Options.OPEN_DIR, after_click),
            pystray.MenuItem(Options.OPEN_FILE, after_click),
            pystray.MenuItem(Options.EXIT, after_click),
        ),
    )

    # Handle system shutdown/logoff events
    def on_system_event(event):
        """
        Gracefully handle system events like shutdown, restart, logoff, and console close.
        Ensures the logger is cleanly terminated before the OS closes the process.
        """
        system_events = {
            win32con.CTRL_C_EVENT: "Ctrl+C",
            win32con.CTRL_BREAK_EVENT: "Ctrl+Break",
            win32con.CTRL_CLOSE_EVENT: "Console window close",
            win32con.CTRL_LOGOFF_EVENT: "User logoff",
            win32con.CTRL_SHUTDOWN_EVENT: "System shutdown",
        }

        if event in system_events:
            event_name = system_events[event]
            log_message(host, f"[System Event] {event_name} - stopping logger")
            halt_event.set()
            time.sleep(2)  # Give thread ~2 seconds to log and exit
            # Return True to indicate we handled the event
            return True

        # For any other events, let the system handle them
        return False

    # Setup ping thread
    def setup_thread(icon):
        ping_thread = threading.Thread(
            target=start_ping_loop,
            args=(icon, host, ignore_seconds, halt_event),
            daemon=False,
        )
        ping_thread.start()
        icon.visible = True

    win32api.SetConsoleCtrlHandler(on_system_event, True)
    try:
        icon.run(setup_thread)
    finally:
        win32api.SetConsoleCtrlHandler(on_system_event, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Internet Connectivity Tester",
        description="Track internet connectivity for a given hostname with 1 second accuracy.",
    )
    parser.add_argument(
        "--host", default="1.1.1.1", help="IP address to ping", type=str
    )
    parser.add_argument(
        "--ignore_seconds",
        default=0,
        help="Seconds to wait before confirming a connection state change (0-60)",
        type=int,
    )
    args = parser.parse_args()

    # Validate IP address
    ip_pattern = re.compile(r"^(((?!25?[6-9])[12]\d|[1-9])?\d\.?\b){4}$")
    if not re.fullmatch(ip_pattern, args.host):
        print(f"Error: '{args.host}' is not a valid IP address")
        sys.exit(1)

    # Validate ignore_seconds
    if not isinstance(args.ignore_seconds, int):
        print("Error: ignore_seconds must be an integer")
        sys.exit(1)

    if not 0 <= args.ignore_seconds <= 60:
        print("Error: ignore_seconds must be between 0 and 60")
        sys.exit(1)

    setup_systray_icon(args.host, args.ignore_seconds)
