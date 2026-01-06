import os
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
import socket
from enum import StrEnum


class Status(StrEnum):
    Online = "Online"
    Timeout = "Timeout"
    Refused = "Refused"
    NetworkError = "Network Error"
    NoRoute = "No Route"

    Started = "Started Log"
    Stopped = "Stopped Log"


def get_script_path():
    return os.path.dirname(__file__)


def get_logs_path():
    log_path = os.path.join(get_script_path(), "logs")
    if not os.path.exists(log_path):
        os.mkdir(log_path)
    return log_path


def get_file_name(host):
    return f"log_{host}.txt"


def sec_to_hms(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(int(seconds)))


def pad_end(string, pad):
    return string + (max(pad - len(string), 0) * " ")


def log_status(logFilePath, host_status_prev, duration=-1, host_status_curr="None"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_message = pad_end(timestamp, 21)
    log_message += pad_end(host_status_prev, 15)
    if duration != -1:
        log_message += pad_end(sec_to_hms(duration), 9)
        log_message += "-> "
        log_message += host_status_curr

    with open(logFilePath, "a") as f:
        f.write(log_message + "\n")


def do_ping(host):
    try:
        with socket.create_connection((host, 443), timeout=2):
            return Status.Online
    except TimeoutError:
        return Status.Timeout
    except ConnectionRefusedError:
        return Status.Refused
    except OSError as e:
        if e.errno in (101, 113):
            return Status.NoRoute
        return Status.NetworkError


def start_ping_loop(icon, host, ignore_seconds, halt_event, logFilePath):
    status_curr = do_ping(host)
    status_prev = Status.Started
    curr_state_sec = 0
    state_diff_sec = None

    start = time.perf_counter()

    log_status(logFilePath, status_prev, curr_state_sec, status_curr)
    status_prev = status_curr

    while True:
        if halt_event.is_set():
            # Log final state and exit immediately
            curr_state_sec = int(time.perf_counter() - start)
            log_status(logFilePath, status_curr, curr_state_sec, Status.Stopped)
            icon.stop()
            return

        status_curr = do_ping(host)
        curr_state_sec = int(time.perf_counter() - start)

        icon.title = f"Host: {host}\n{status_prev} : {sec_to_hms(curr_state_sec)}"

        # If status changed from the logged state
        if status_curr != status_prev:
            # First time detecting this change
            if state_diff_sec is None:
                state_diff_sec = time.perf_counter()

            # Check if enough time has passed to confirm the change
            time_elapsed = time.perf_counter() - state_diff_sec
            if time_elapsed >= ignore_seconds:
                curr_state_sec = int(time.perf_counter() - start)
                log_status(logFilePath, status_prev, curr_state_sec, status_curr)
                status_prev = status_curr
                start = time.perf_counter()
                state_diff_sec = None
        else:
            # Status returned to the logged state, reset the change timer
            state_diff_sec = None

        time.sleep(1)


class Options:
    OPEN_DIR = "Open Logger Directory"
    OPEN_FILE = "Open Logger File"
    EXIT = "Exit"


def setup_systray_icon(host, ignore_seconds):
    # Load icon
    iconPath = os.path.join(get_script_path(), "globe-svgrepo-com.png")
    logFilePath = os.path.join(get_logs_path(), get_file_name(host))
    if not os.path.exists(iconPath):
        log_status(logFilePath, "Error: Icon file not found")
        sys.exit()

    image = Image.open(iconPath)

    # Setup state and callbacks
    halt_event = threading.Event()
    log_status(logFilePath, f"Running. Ignoring {ignore_seconds}s")

    def after_click(icon, query):
        query_str = str(query)
        match query_str:
            case Options.OPEN_DIR:
                os.startfile(get_script_path())
            case Options.OPEN_FILE:
                if not os.path.exists(logFilePath):
                    log_status(logFilePath, "Error: Log file not found")
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
            log_status(
                logFilePath, f"[System Event] {event_name} - {str(Status.Stopped)}"
            )
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
            args=(icon, host, ignore_seconds, halt_event, logFilePath),
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
