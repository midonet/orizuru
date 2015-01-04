BUGS
====

paramiko fails with a ssh fingerprint error (even though host key checking is off) when you use a config with proxycommand and have not logged into the man-in-the-middle host before with ssh.

you should make sure you have the fingerprints of the server hosts in your ssh/known_hosts file before starting the installer

