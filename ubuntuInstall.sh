#!/bin/bash

echo "Dependencies: make gcc libtool autoconf libpam-dev pep8 usermode python-ethtool python-dev python-dbus"
echo "Please resolve the dependencies manually by apt-get install them, then run this script to build and install ovirt guest agent."
echo "[Press ENTER to continue]"
read

[ -e Makefile ] && make clean
[ -e Makefile.in ] && make distclean

set -e
./autogen.sh
./configure --with-sso=no --prefix=/usr --sysconfdir=/etc --localstatedir=/var
make
set +e

sudo stop ovirt-guest-agent >/dev/null 2>&1

sudo make install

getent group ovirtagent >/dev/null || sudo groupadd -r -g 175 ovirtagent
getent passwd ovirtagent > /dev/null || \
    sudo /usr/sbin/useradd -u 175 -g 175 -o -r ovirtagent \
    -c "oVirt Guest Agent" -d /usr/share/ovirt-guest-agent -s /sbin/nologin

# get rid of the error
# org.freedesktop.DBus.Error.AccessDenied: Connection ":1.88" is not allowed to own the service
sudo adduser ovirtagent netdev >/dev/null 2>&1

sudo udevadm control  --reload-rules
sudo udevadm trigger --subsystem-match="virtio-ports" \
    --attr-match="name=com.redhat.rhevm.vdsm"
sudo udevadm settle
sudo install -D -m 0644 -o root -g root ovirt-guest-agent/ovirt-guest-agent.upstart.conf /etc/init/ovirt-guest-agent.conf

sudo chmod +x /usr/share/ovirt-guest-agent/hibernate
sudo chmod +x /usr/share/ovirt-guest-agent/LockActiveSession.{py,pyc}

sudo start ovirt-guest-agent

exit 0
