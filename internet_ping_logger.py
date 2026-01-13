import os
import errno
import threading
import time
from datetime import datetime
import re
import sys
import argparse
import pystray
from PIL import Image
import time
import socket
from enum import StrEnum


class Status(StrEnum):
    # Max string length for log_status = 18
    # Online
    Online = "Online"

    # Network errors
    Timeout = "Timeout"
    NetUnreachable = "Net Unreachable"

    # Host errors
    Refused = "Refused"
    Aborted = "Aborted"
    Reset = "Reset"

    # Operating system errors
    NoRoute = "No Route"
    HostUnreachable = "Host Unreachable"

    Started = "Started Log"
    Stopped = "Stopped Log"


def get_script_path():
    return os.path.dirname(__file__)


def get_log_file_path(host):
    log_path = os.path.join(get_script_path(), "logs")
    if not os.path.exists(log_path):
        os.mkdir(log_path)
    return os.path.join(log_path, f"log_{host}.txt")


def sec_to_hms(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(int(seconds)))


def log_new_status(log_file_path: str, curr_status: str, duration: int | None = None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    part_duration = ""
    if duration:
        part_duration = "   " + sec_to_hms(duration)

    part_curr_status = [timestamp, curr_status.rjust(18)]

    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write(part_duration + "\n" + "   ".join(part_curr_status))


def do_ping(host) -> tuple[str, int]:
    # If problem with network, return 2
    # If problem with connection to host and network OK, return 1
    # If no issue, return 0
    try:
        with socket.create_connection((host, 443), timeout=2):
            return (Status.Online, 0)
    except TimeoutError:
        return (Status.Timeout, 2)
    except ConnectionRefusedError:
        return (Status.Refused, 1)
    except ConnectionAbortedError:
        return (Status.Aborted, 1)
    except ConnectionResetError:
        return (Status.Reset, 1)
    except OSError as e:
        if e.errno in (101, 113):
            return (Status.NoRoute, 2)
        if e.errno == 10065:
            # E 10065:A socket operation was attempted to an unreachable host
            return (Status.NetUnreachable, 2)
        if e.errno == 10051:
            # E 10051:A socket operation was attempted to an unreachable network
            return (Status.HostUnreachable, 1)
        # Errors to account for should they not be handled
        return (f"E {e.errno}:{e.strerror}", 2)


def start_ping_loop(icon, host, ignore_seconds, halt_event, logFilePath, images):
    status_curr, status_image_index = do_ping(host)
    status_prev = status_curr
    curr_state_sec = 0
    state_diff_sec = None
    time_elapsed = 0

    start = time.perf_counter()

    log_new_status(logFilePath, status_curr)
    icon.icon = images[status_image_index]

    while True:
        if halt_event.is_set():
            # Log final state and exit immediately
            curr_state_sec = int(time.perf_counter() - start)
            log_new_status(logFilePath, Status.Stopped, curr_state_sec)
            icon.stop()
            return

        status_curr, status_image_index = do_ping(host)
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
                icon.icon = images[status_image_index]
                curr_state_sec = int(time.perf_counter() - start)
                log_new_status(logFilePath, status_curr, curr_state_sec)
                status_prev = status_curr
                start = time.perf_counter()
                state_diff_sec = None
        else:
            # Status returned to the logged state, reset the change timer
            state_diff_sec = None

        time.sleep(1)


def setup_systray_icon(host, ignore_seconds):
    # Load icon
    iconPath = os.path.join(get_script_path(), "tray_icons_png")
    icons = [
        "internet_good.png",
        "internet_warning.png",
        "internet_none.png",
    ]
    logFilePath = get_log_file_path(host)

    for icon in icons:
        if not os.path.exists(os.path.join(iconPath, icon)):
            log_new_status(logFilePath, f"Error: Icon file not found {icon}")
            sys.exit()

    images = [Image.open(os.path.join(iconPath, icon)) for icon in icons]
    # Setup state and callbacks
    halt_event = threading.Event()
    log_new_status(logFilePath, f"Init ignoring: {ignore_seconds}s")

    def menu_open_dir():
        os.startfile(get_script_path())

    def menu_open_file():
        if not os.path.exists(logFilePath):
            log_new_status(logFilePath, "Error: Log file not found")
            sys.exit()
        os.startfile(logFilePath)

    def menu_exit():
        halt_event.set()

    # Create icon with menu
    icon = pystray.Icon(
        "Python Internet Ping Logger",
        images[0],
        "Booting InternetPingLogger",
        menu=pystray.Menu(
            pystray.MenuItem("Open Logger Directory", menu_open_dir),
            pystray.MenuItem("Open Logger File", menu_open_file),
            pystray.MenuItem("Exit", menu_exit),
        ),
    )

    # Handle system shutdown/logoff events
    # Tried signal.signal, atexit, python doesn't receive signals from windows for proper shutdown

    # Setup ping thread
    def setup_thread(icon):
        ping_thread = threading.Thread(
            target=start_ping_loop,
            args=(icon, host, ignore_seconds, halt_event, logFilePath, images),
            daemon=False,
        )
        ping_thread.start()
        icon.visible = True

    icon.run(setup_thread)


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
        default=2,
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
