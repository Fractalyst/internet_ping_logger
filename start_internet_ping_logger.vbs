Set WshShell = CreateObject("WScript.Shell")

cmd = """py.exe"" ""internet_ping_logger.py"" --host 1.1.1.1 --ignore_seconds 2"

WshShell.Run cmd, 0