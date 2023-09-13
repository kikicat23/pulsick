pulsick: automate Ivanti / Pulse Secure log-in on Linux
by kikicat

Want to avoid entering VPN password and OTP every X hours, and have continuous VPN connection ?

The Ivanti / Pulse Secure client should be started (in an vncserver instance for example) and connected before proceeding.

The following will automate server re-login requests, getting password and OTP through pass[1] and pass-otp[2]:
DISPLAY=:1.0 ./pulsick.py -v myuser "pass vpn-password" "pass otp vpn-otp"

If the server implements pre-auth notification, use -p.

[1] https://www.passwordstore.org/
[2] https://github.com/tadfisher/pass-otp

Dependencies
------------

# apt install python3-xlib

Usage
-----

$ ./pulsick.py --help
usage: pulsick.py [-h] [-p] [-v] login password_cmd otp_cmd

automate Ivanti / Pulse Secure log-in on Linux

positional arguments:
  login                Login
  password_cmd         Command to execute to get password
  otp_cmd              Command to execute to get OTP

options:
  -h, --help           show this help message and exit
  -p, --preauth-notif  confirm the pre-auth notification
  -v, --verbose
