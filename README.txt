pulsik: automate Ivanti / Pulse Secure log-in on Linux
by kikicat

Want to avoid entering VPN password and OTP every X hours, and have continuous VPN connection ?

Example usage, getting password and OTP through pass[1] and pass-otp[2]:
DISPLAY=:1.0 ./pulsick.py -v myuser "pass vpn-password" "pass otp vpn-otp"

[1] https://www.passwordstore.org/
[2] https://github.com/tadfisher/pass-otp
