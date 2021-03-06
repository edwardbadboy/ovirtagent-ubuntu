#
# Copyright 2010-2013 Red Hat, Inc. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Refer to the README and COPYING files for full details of the license.
#

import os
import platform
import time
import sys


# avoid pep8 warnings
def import_json():
    try:
        import json
        return json
    except ImportError:
        import simplejson
        return simplejson
json = import_json()


# Set taken from http://www.w3.org/TR/xml11/#NT-RestrictedChar
__RESTRICTED_CHARS = set(range(8 + 1)).union(
    set(range(0xB, 0xC + 1))).union(
        set(range(0xE, 0x1F + 1))).union(
            set(range(0x7F, 0x84 + 1))).union(
                set(range(0x86, 0x9F + 1)))


def _string_check(str):
    """
    This function tries to convert the given string to a valid representable
    form. Normal and valid unicode strings should not fail this test. Invalid
    encodings will fail this and might get characters replaced.
    """
    try:
        str.encode(sys.stdout.encoding, 'strict')
    except UnicodeError:
        try:
            return str.encode('ascii', 'replace')
        except UnicodeError:
            # unrepresentable string
            return unicode()
    return str


def _filter_xml_chars(u):
    """
    Filter out restricted xml chars from unicode string. Not using
    Python's xmlcharrefreplace because it accepts '\x01', which
    the spec frown upon.
    """
    def mask_restricted(c):
        if ord(c) in __RESTRICTED_CHARS:
            return '?'
        else:
            return c

    return ''.join(mask_restricted(c) for c in u)


def _filter_object(obj):
    """
    Apply _filter_xml_chars and _string_check on all strings in the given
    object
    """
    def filt(o):
        if isinstance(o, dict):
            return dict(map(filt, o.iteritems()))
        if isinstance(o, list):
            return map(filt, o)
        if isinstance(o, tuple):
            return tuple(map(filt, o))
        if isinstance(o, basestring):
            return _filter_xml_chars(_string_check(o))
        return o

    return filt(obj)


class VirtIoChannel:

    # Python on Windows 7 returns 'Microsoft' rather than 'Windows' as
    # documented.
    is_windows = platform.system() in ['Windows', 'Microsoft']

    def __init__(self, vport_name):
        if self.is_windows:
            from WinFile import WinFile
            self._vport = WinFile(vport_name)
        else:
            self._vport = os.open(vport_name, os.O_RDWR)
        self._buffer = ''

    def _readbuffer(self):
        if self.is_windows:
            buffer = self._vport.read(4096)
        else:
            buffer = os.read(self._vport, 4096)
        if buffer:
            self._buffer += buffer
        else:
            # read() returns immediately (non-blocking) if no one is
            # listening on the other side of the virtio-serial port.
            # So in order not to be in a tight-loop and waste CPU
            # time, we just sleep for a while and hope someone will
            # be there when we will awake from our nap.
            time.sleep(1)

    def _readline(self):
        newline = self._buffer.find('\n')
        while newline < 0:
            self._readbuffer()
            newline = self._buffer.find('\n')
        if newline >= 0:
            line, self._buffer = self._buffer.split('\n', 1)
        else:
            line = None
        return line

    def _parseLine(self, line):
        try:
            args = json.loads(line.decode('utf8'))
            name = args['__name__']
            del args['__name__']
        except:
            name = None
            args = None
        return (name, args)

    def read(self):
        return self._parseLine(self._readline())

    def write(self, name, args={}):
        if not isinstance(name, str):
            raise TypeError("1nd arg must be a str.")
        if not isinstance(args, dict):
            raise TypeError("2nd arg must be a dict.")
        args['__name__'] = name
        args = _filter_object(args)
        message = (json.dumps(args) + '\n').encode('utf8')
        filtered_message = _filter_xml_chars(message)
        # Sanity check only, on purpose we're throwing away the string
        # to ensure we've produced a decodable utf-8 string after filtering
        filtered_message.decode('utf-8')
        message = filtered_message
        while len(message) > 0:
            if self.is_windows:
                written = self._vport.write(message)
            else:
                written = os.write(self._vport, message)
            message = message[written:]


def _create_vio():
    if (platform.system() == 'Windows') or (platform.system() == 'Microsoft'):
        vport_name = '\\\\.\\Global\\com.redhat.rhevm.vdsm'
    else:
        vport_name = '/dev/virtio-ports/com.redhat.rhevm.vdsm'
    return VirtIoChannel(vport_name)


def _test_write():
    vio = _create_vio()
    vio.write('network-interfaces',
              {'interfaces': [{
                  'name': 'eth0',
                  'inet': ['10.0.0.2'],
                  'inet6': ['fe80::213:20ff:fef5:f9d6'],
                  'hw': '00:1a:4a:23:10:00'}]})
    vio.write('applications', {'applications': ['kernel-2.6.32-131.4.1.el6',
                                                'rhev-agent-2.3.11-1.el6']})


def _test_read():
    vio = _create_vio()
    line = vio.read()
    while line:
        print line
        line = vio.read()

if __name__ == "__main__":
    _test_read()
