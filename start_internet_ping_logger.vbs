Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """.venv\Scripts\python.exe"" ""InternetPingLogger.py"" --host 1.1.1.1 --ignore_seconds 2", 0

