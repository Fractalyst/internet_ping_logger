# InternetPingLogger

## Version 1.0

**InternetPingLogger** is a small Windows tray application that monitors the reachability of a given IP address by attempting a TCP connection on port 443 once per second. It logs all connectivity state changes:

**Online**, **Timeout**, **Refused**, **Abored**, **Reset**, **No Route** , **Net Unreachable** 

This, with timestamps and how long each state lasted are logged. Logs are saved as JSON-line array entries inside a file named **log_X.X.X.X.txt** in the script directory in **logs\\** folder. A system tray icon displays the current state duration and provides quick actions such as opening the log file, opening the log directory, or exiting the application.

You can configure an optional **--ignore_seconds** value to prevent brief fluctuations from being logged. For example, if the host appears unreachable for only one or two seconds, setting **--ignore_seconds 3** will ignore the temporary change unless it persists for at least 3 seconds. The application also gracefully handles system shutdown, console close, and Ctrl+C events, ensuring that final state information is written before exiting. A shortcut pointing to **start_internet_ping_logger.vbs** can be placed in your windows startup folder to track all internet status when computer is on.

## Note for IP Address to ping

❌ Google ```8.8.8.8```

✔️ Cloudflare (default) ```1.1.1.1```

## Requirements

### Requires Python to be installed

https://www.python.org/downloads/

## Usage

### Windows

Run the script by double-clicking **start_internet_ping_logger.vbs**

### Command line (Windows or Linux)

Run the script from the command line:

```python internet_ping_logger.py --host <IP> --ignore_seconds <0–60>```

## Arguments

--host (required) — IPv4 address to monitor.

--ignore_seconds (optional, default 2s) — Seconds a state change must persist before it is logged (0–60).

Example:

```python internet_ping_logger.py --host 1.1.1.1 --ignore_seconds 3```

This launches the tray application, begins logging state changes, and generates logs\log_1.1.1.1.txt.