# vim: set expandtab shiftwidth=4 tabstop=4:
#
# Copyright 2016 Red Hat, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice (including the next
# paragraph) shall be included in all copies or substantial portions of the
# Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from gi.repository import GLib
from gi.repository import Gio

class RatbagdDBusUnavailable(BaseException):
    """
    Signals DBus is unavailable or the ratbagd daemon is not available.
    """
    pass

class _RatbagdDBus(object):
    def __init__(self, interface, object_path):
        self._dbus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        if self._dbus is None:
            raise RatbagdDBusUnavailable()

        try:
            self._proxy = Gio.DBusProxy.new_sync(self._dbus,
                                                 Gio.DBusProxyFlags.NONE,
                                                 None,
                                                 'org.freedesktop.ratbag1',
                                                 object_path,
                                                 'org.freedesktop.ratbag1.{}'.format(interface),
                                                 None)
        except GLib.GError:
            raise RatbagdDBusUnavailable()

        if self._proxy.get_name_owner() is None:
            raise RatbagdDBusUnavailable()

    def dbus_property(self, property):
        p = self._proxy.get_cached_property(property)
        if p != None:
            return p.unpack()
        return p

    def dbus_call(self, method, type, *value):
        val = GLib.Variant("({})".format(type), value)
        res = self._proxy.call_sync(method, val, Gio.DBusCallFlags.NO_AUTO_START, 500, None)
        if res != None:
            return res.unpack()
        return res

class Ratbagd(_RatbagdDBus):
    """
    The ratbagd top-level object. Provides a list of devices available
    through ratbagd; actual interaction with the devices is via the
    RatbagdDevice, RatbagdProfile, RatbagdResolution and RatbagdButton objects.

    Throws RatbagdDBusUnavailable when the DBus service is not available.
    """
    def __init__(self):
        _RatbagdDBus.__init__(self, "Manager", '/org/freedesktop/ratbag1')
        self._devices = []
        result = self.dbus_property("Devices")
        if result != None:
            self._devices = [RatbagdDevice(objpath) for objpath in result]

    @property
    def devices(self):
        """
        A list of RatbagdDevice objects supported by ratbagd.
        """
        return self._devices
    # TODO: DeviceNew, DeviceRemoved

class RatbagdDevice(_RatbagdDBus):
    """
    Represents a ratbagd device.
    """

    CAP_NONE = 0
    CAP_QUERY_CONFIGURATION = 1
    CAP_RESOLUTION = 100
    CAP_SWITCHABLE_RESOLUTION = 101
    CAP_PROFILE = 200
    CAP_SWITCHABLE_PROFILE = 201
    CAP_DISABLE_PROFILE = 202
    CAP_DEFAULT_PROFILE = 203
    CAP_BUTTON = 300
    CAP_BUTTON_KEY = 301
    CAP_BUTTON_MACROS = 302
    CAP_LED = 400

    def __init__(self, object_path):
        _RatbagdDBus.__init__(self, "Device", object_path)
        self._objpath = object_path
        self._devnode = self.dbus_property("Id")
        self._caps = self.dbus_property("Capabilities")
        self._description = self.dbus_property("Description")
        self._svg = self.dbus_property("Svg")
        self._svg_path = self.dbus_property("SvgPath")

        self._profiles = []
        self._active_profile = -1
        result = self.dbus_property("Profiles")
        if result != None:
            self._profiles = [RatbagdProfile(objpath) for objpath in result]
            self._active_profile = self.dbus_property("ActiveProfile")

    @property
    def id(self):
        """
        The unique identifier of this device.
        """
        return self._devnode

    @property
    def capabilities(self):
        """
        The capabilities of this device as an array. Capabilities not present on
        the device are not in the list. Thus use e.g.
            if RatbagdDevice.CAP_SWITCHABLE_RESOLUTION is in device.capabilities:
                 do something
        """
        return self._caps

    @property
    def description(self):
        """
        The device name, usually provided by the kernel.
        """
        return self._description

    @property
    def svg(self):
        """
        The SVG file name. This function returns the file name only, not the
        absolute path to the file.
        """
        return self._svg

    @property
    def svg_path(self):
        """
        The full, absolute path to the SVG.
        """
        return self._svg_path

    @property
    def profiles(self):
        """
        A list of RatbagdProfile objects provided by this device.
        """
        return self._profiles

    @property
    def active_profile(self):
        """
        The currently active profile. This function returns a RatbagdProfile
        or None if no active profile was found.
        """
        if self._active_profile == -1:
            return None
        return self._profiles[self._active_profile]

    def get_profile_by_index(self, index):
        """
        Returns the profile found at the given index, or None if no profile was
        found.
        """
        return self.dbus_call("GetProfileByIndex", "u", index)

    def __eq__(self, other):
        return other and self._objpath == other._objpath

class RatbagdProfile(_RatbagdDBus):
    """
    Represents a ratbagd profile.
    """

    def __init__(self, object_path):
        _RatbagdDBus.__init__(self, "Profile", object_path)
        self._objpath = object_path
        self._index = self.dbus_property("Index")
        self._resolutions = []
        self._buttons = []
        self._active_resolution_index = -1
        self._default_resolution_index = -1

        result = self.dbus_property("Resolutions")
        if result != None:
            self._resolutions = [RatbagdResolution(objpath) for objpath in result]
            self._active_resolution_index = self.dbus_property("ActiveResolution")
            self._default_resolution_index = self.dbus_property("DefaultResolution")

        result = self.dbus_property("Buttons")
        if result != None:
            self._buttons = [RatbagdButton(objpath) for objpath in result]

    @property
    def index(self):
        """
        The index of this profile.
        """
        return self._index

    @property
    def resolutions(self):
        """
        A list of RatbagdResolution objects with this profile's resolutions.
        """
        return self._resolutions

    @property
    def buttons(self):
        """
        A list of RatbagdButton objects with this profile's button
        mappings. Note that the list of buttons differs between profiles but
        the number of buttons is identical across profiles.
        """
        return self._buttons

    @property
    def active_resolution(self):
        """
        The currently active resolution. This function returns a
        RatbagdResolution object or None.
        """
        if self._active_resolution_index == -1:
            return None
        return self._resolutions[self._active_resolution_index]

    @property
    def default_resolution(self):
        """
        The default resolution. This function returns a RatbagdResolution
        object or None.
        """
        if self._default_resolution_index == -1:
            return None
        return self._resolutions[self._default_resolution_index]

    def set_active(self):
        """
        Set this profile to be the active profile.
        """
        return self.dbus_call("SetActive", "")

    def get_resolution_by_index(self, index):
        """
        Returns the resolution found at the given index. This function returns a
        RatbagdResolution or None if no resolution was found.
        """
        return self.dbus_call("GetResolutionByIndex", "u", index)

    # TODO: active profile changed

    def __eq__(self, other):
        return self._objpath == other._objpath

class RatbagdResolution(_RatbagdDBus):
    """
    Represents a ratbagd resolution.
    """

    CAP_INDIVIDUAL_REPORT_RATE = 1
    CAP_SEPARATE_XY_RESOLUTION = 2

    def __init__(self, object_path):
        _RatbagdDBus.__init__(self, "Resolution", object_path)
        self._objpath = object_path
        self._index = self.dbus_property("Index")
        self._caps = self.dbus_property("Capabilities")
        self._xres = self.dbus_property("XResolution")
        self._yres = self.dbus_property("YResolution")
        self._rate = self.dbus_property("ReportRate")

    @property
    def index(self):
        """The index of this resolution."""
        return self._index

    @property
    def capabilities(self):
        """
        The capabilities of this resolution as a list. Capabilities not present
        on the resolution are not in the list. Thus use e.g.
            if RatbagdResolution.CAP_SEPARATE_XY_RESOLUTION is in resolution.capabilities:
                 do something
        """
        return self._caps

    @property
    def resolution(self):
        """
        The tuple (xres, yres) with each resolution in DPI.
        """
        return (self._xres, self._yres)

    @resolution.setter
    def resolution(self, res):
        """
        Set the x- and y-resolution using the given (xres, yres) tuple.
        """
        return self.dbus_call("SetResolution", "uu", *res)

    @property
    def report_rate(self):
        """
        The report rate in Hz.
        """
        return self._rate

    @report_rate.setter
    def report_rate(self, rate):
        """
        Set the report rate in Hz.
        """
        return self.dbus_call("SetReportRate", "u", rate)

    def set_default(self):
        """
        Set this resolution to be the default.
        """
        return self.dbus_call("SetDefault", "")

    # TODO: ActiveResolutionChanged, DefaultResolutionChanged

    def __eq__(self, other):
        return self._objpath == other._objpath

class RatbagdButton(_RatbagdDBus):
    """
    Represents a ratbagd button.
    """
    def __init__(self, object_path):
        _RatbagdDBus.__init__(self, "Button", object_path)
        self._objpath = object_path
        self._index = self.dbus_property("Index")
        self._type = self.dbus_property("Type")
        self._button = self.dbus_property("ButtonMapping")
        self._special = self.dbus_property("SpecialMapping")
        self._key = self.dbus_property("KeyMapping")
        self._action = self.dbus_property("ActionType")
        self._types = self.dbus_property("ActionTypes")

    @property
    def index(self):
        """
        The index of this button.
        """
        return self._index

    @property
    def button_type(self):
        """
        A string describing this button's type.
        """
        return self._type

    @property
    def button_mapping(self):
        """
        An integer of the current button mapping, if mapping to a button.
        """
        return self._button

    @button.setter
    def button(self, button):
        """
        Set the button mapping to the given button.
        """
        return self.dbus_call("SetButtonMapping", "u", button)

    @property
    def special(self):
        """
        A string of te current special mapping, if mapped to special.
        """
        return self._special

    @special.setter
    def special(self, special):
        """
        Set the button mapping to the given special entry.
        """
        return self.dbus_call("SetSpecialMapping", "s", special)

    @property
    def key(self):
        """
        An array of integers, the first being the keycode and the other entries,
        if any, are modifiers (if mapped to key).
        """
        return self._key

    @key.setter
    def key(self, key, modifiers):
        """
        Set the key mapping. The first entry is the keycode, other entries (if
        any), are modifier keycodes.
        """
        return self.dbus_call("SetKeyMapping", "au", [key].append(modifiers))

    @property
    def action_type(self):
        """
        A string describing the action type of the button. One of "none",
        "button", "key", "special", "macro" or "unknown". This decides which
        *Mapping property has a value.
        """
        return self._action

    @property
    def action_types(self):
        """
        An array of possible values for ActionType.
        """
        return self._types

    def disable(self):
        """
        Disable this button.
        """
        return self.dbus_call("Disable", "")
