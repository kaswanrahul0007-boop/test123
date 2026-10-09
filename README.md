# Hello website

HTTPS server that prints a hello message.

    sudo python3 server.py          # https://131.1.65.123:443

Override with `HOST=... PORT=... python3 server.py`. A self-signed certificate is generated on first run (browsers will warn); supply your own via `CERT`/`KEY`.
The host IP must be assigned to a local network interface, and port 443 requires root.
