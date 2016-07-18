__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import wx
import ConfigParser as configparser
import os.path

from Cura.util import profile
from Cura.util import resources
from Cura.gui import mexPanel
from Cura.gui import idexPanel
from Cura.gui import configBase

class ProfileInfo(object):
    def __init__(self, filename):
        self.filename = filename
        self.base_filename = os.path.splitext(os.path.basename(filename))[0]
        cp = configparser.ConfigParser()
        cp.read(filename)

        self.name = self.base_filename
        self.material = None
        self.nozzle_size = None
        self.order = 0

        if cp.has_option('info', 'name'):
            self.name = cp.get('info', 'name')
        if cp.has_option('info', 'material'):
            self.material = cp.get('info', 'material')
        if cp.has_option('info', 'nozzle_size'):
            self.nozzle_size = cp.get('info', 'nozzle_size')
        if cp.has_option('info', 'nozzle_size'):
            self.order = int(cp.get('info', 'order'))

class ProfileManager(object):
    def __init__(self):
        self._print_profiles = []
        self._material_profiles = []
        self._material_in_print_profile = False
        for filename in resources.getSimpleModeProfiles(profile.getMachineSetting('machine_type')):
            pi = ProfileInfo(filename)
            self._print_profiles.append(pi)
            if pi.material is not None:
                self._material_in_print_profile = True

        if not self._material_in_print_profile and profile.getMachineSetting('gcode_flavor') != 'UltiGCode':
            for filename in resources.getSimpleModeMaterials():
                pi = ProfileInfo(filename)
                self._material_profiles.append(pi)

        self._print_profiles.sort(cmp=lambda a, b: a.order - b.order)
        self._material_profiles.sort(cmp=lambda a, b: a.order - b.order)

    def getProfileNames(self):
        ret = []
        for profile in self._print_profiles:
            if profile.name not in ret:
                ret.append(profile.name)
        return ret

    def getMaterialNames(self):
        ret = []
        if self._material_in_print_profile:
            for profile in self._print_profiles:
                if profile.material is not None and profile.material not in ret:
                    ret.append(profile.material)
        else:
            for profile in self._material_profiles:
                if profile.name not in ret:
                    ret.append(profile.name)
        return ret

    def getNozzleSizes(self):
        ret = []
        for profile in self._print_profiles:
            if profile.nozzle_size is not None and profile.nozzle_size not in ret:
                ret.append(profile.nozzle_size)
        return ret

    def isValidProfileOption(self, profile_name, material_name, nozzle_size):
        return self._getProfileFor(profile_name, material_name, nozzle_size) is not None

    def getSettingsFor(self, profile_name, material_name, nozzle_size):
        settings = {}

        current_profile = self._getProfileFor(profile_name, material_name, nozzle_size)
        cp = configparser.ConfigParser()
        cp.read(current_profile.filename)
        for setting in profile.settingsList:
            if setting.isProfile():
                if cp.has_option('profile', setting.getName()):
                    settings[setting.getName()] = cp.get('profile', setting.getName())

        if not self._material_in_print_profile:
            for current_profile in self._material_profiles:
                if current_profile.name == material_name:
                    cp = configparser.ConfigParser()
                    cp.read(current_profile.filename)
                    for setting in profile.settingsList:
                        if setting.isProfile():
                            if cp.has_option('profile', setting.getName()):
                                settings[setting.getName()] = cp.get('profile', setting.getName())

        return settings

    def _getProfileFor(self, profile_name, material_name, nozzle_size):
        if self._material_in_print_profile:
            for profile in self._print_profiles:
                if profile.name == profile_name and profile.material == material_name and nozzle_size == profile.nozzle_size:
                    return profile
        else:
            for profile in self._print_profiles:
                if profile.name == profile_name and nozzle_size == profile.nozzle_size:
                    return profile
        return None

class simpleModePanel(configBase.configPanelBase):
    "Main user interface window for Quickprint mode"
    def __init__(self, parent, callback = None):
        super(simpleModePanel, self).__init__(parent, callback)

        # Main tabs
        self.nb = wx.Notebook(self)
        self.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
        self.GetSizer().Add(self.nb, 1, wx.EXPAND)

        #self._callback = callback

        self.pluginPanel = mexPanel.pluginPanel(self.nb, callback)
        self.nb.AddPage(self.pluginPanel, _("MEX"))

        self.alterationPanel = idexPanel.alterationPanel(self.nb, callback)
        self.nb.AddPage(self.alterationPanel, "IDEX")

        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.nb.SetSize(self.GetSize())

    def OnSize(self, e):
        # Make the size of the Notebook control the same size as this control
        self.nb.SetSize(self.GetSize())

        # Propegate the OnSize() event (just in case)
        e.Skip()

    def UpdateSize(self, configPanel):
        sizer = configPanel.GetSizer()

        # Pseudocde
        # if horizontal:
        #     if width(col1) < best_width(col1) || width(col2) < best_width(col2):
        #         switch to vertical
        # else:
        #     if width(col1) > (best_width(col1) + best_width(col1)):
        #         switch to horizontal
        #

        col1 = configPanel.leftPanel
        colSize1 = col1.GetSize()
        colBestSize1 = col1.GetBestSize()
        col2 = configPanel.rightPanel
        colSize2 = col2.GetSize()
        colBestSize2 = col2.GetBestSize()

        orientation = sizer.GetOrientation()

        if orientation == wx.HORIZONTAL:
            if (colSize1[0] <= colBestSize1[0]) or (colSize2[0] <= colBestSize2[0]):
                configPanel.Freeze()
                sizer = wx.BoxSizer(wx.VERTICAL)
                sizer.Add(configPanel.leftPanel, flag=wx.EXPAND)
                sizer.Add(configPanel.rightPanel, flag=wx.EXPAND)
                configPanel.SetSizer(sizer)
                # sizer.Layout()
                configPanel.Layout()
                self.Layout()
                configPanel.Thaw()
        else:
            if max(colSize1[0], colSize2[0]) > (colBestSize1[0] + colBestSize2[0]):
                configPanel.Freeze()
                sizer = wx.BoxSizer(wx.HORIZONTAL)
                sizer.Add(configPanel.leftPanel, proportion=1, border=35, flag=wx.EXPAND)
                sizer.Add(configPanel.rightPanel, proportion=1, flag=wx.EXPAND)
                configPanel.SetSizer(sizer)
                # sizer.Layout()
                configPanel.Layout()
                self.Layout()
                configPanel.Thaw()