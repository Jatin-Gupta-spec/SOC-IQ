"""
Reusable sample reports for automated testing.
"""

SAMPLE_REPORT = """
Connection from 192.168.1.10

DNS lookup:
evilcorp.com

Download:
https://evilcorp.com/payload.exe

Email:
attacker@evilcorp.com

MD5:
44d88612fea8a8f36de82e1278abb02f

SHA1:
7c4a8d09ca3762af61e59520943dc26494f8941b

SHA256:
3f786850e387550fdab836ed7e6dc881de23001b4fb5d6fcb5b8f8f9d4f6b6c5

CVE:
CVE-2024-4577

Windows File:
C:\\Windows\\System32\\cmd.exe

Registry:
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
"""

DUPLICATE_IPV4_REPORT = """
8.8.8.8

8.8.8.8

8.8.8.8
"""

NO_IPV4_REPORT = """
evilcorp.com

attacker@evilcorp.com
"""