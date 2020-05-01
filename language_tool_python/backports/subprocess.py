"""Some backported features for subprocess."""

from __future__ import absolute_import

import sys
import time

from subprocess import Popen, PIPE, STDOUT, check_call, check_output

# For pyflakes.
check_call
check_output
PIPE
STDOUT

if sys.platform == 'win32':
    from subprocess import STARTF_USESHOWWINDOW, STARTUPINFO
    # For pyflakes.
    STARTF_USESHOWWINDOW
    STARTUPINFO


if sys.version_info[0] == 2:
    class SubprocessError(Exception):

        """Exception classes used by this module."""

    class TimeoutExpired(SubprocessError):

        """Raised when the timeout expires while waiting for a child
        process."""

        def __init__(self, cmd, timeout, output=None):
            self.cmd = cmd
            self.timeout = timeout
            self.output = output

        def __str__(self):
            return ("Command '%s' timed out after %s seconds" %
                    (self.cmd, self.timeout))

    def Popen_init(self, args, *args_, **kwargs):
        """Create new Popen instance."""
        _Popen_init(self, args, *args_, **kwargs)
        self.args = args

    def Popen_wait(self, timeout=None):
        """Wait for child process to terminate."""
        if timeout is None:
            return _Popen_wait(self)
        deadline = time.time() + timeout
        while self.poll() is None:
            if time.time() > deadline:
                raise TimeoutExpired(self.args, timeout)
            time.sleep(0.01)
        return self.returncode

    def Popen_communicate(self, input=None, timeout=None):
        """Interact with process."""
        if timeout is not None:
            self.wait(timeout)
        return _Popen_communicate(self, input)

    _Popen_init = Popen.__init__
    _Popen_wait = Popen.wait
    _Popen_communicate = Popen.communicate
    Popen.__init__ = Popen_init
    Popen.wait = Popen_wait
    Popen.communicate = Popen_communicate
