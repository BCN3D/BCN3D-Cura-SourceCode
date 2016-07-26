__author__ = 'rmelbourne'

import wx
import ConfigParser as configparser
import os.path

from Cura.util import profile
from Cura.util import resources

class ProfileInfo(object):
    def __init__(self, filename):
        self.filename = filename
        self.base_filename = os.path.splitext(os.path.basename(filename))[0]
        cp = configparser.ConfigParser()
        cp.read(filename)

        self.name = self.base_filename
        self.material_left = None
        self.material_right = None
        self.order = 0

        if cp.has_option('info', 'name'):
            self.name = cp.get('info', 'name')
        if cp.has_option('info', 'material_left'):
            self.material_left = cp.get('info', 'material_left')
        if cp.has_option('info', 'material_right'):
            self.material_right = cp.get('info', 'material_right')

class ProfileManager(object):
    def __init__(self):
        self._print_profiles = []
        self._material_left_profiles = []
        self._material_right_profiles = []
        self._material_in_print_profile = False

        for filename in resources.getSimpleModeProfiles(profile.getMachineSetting('machine_type') + 'idex'):
            pi = ProfileInfo(filename)
            self._print_profiles.append(pi)
            if pi.material_left is not None and pi.material_right is not None:
                self._material_in_print_profile = True

        self._print_profiles.sort(cmp=lambda a, b: a.order - b.order)
        self._material_left_profiles.sort(cmp=lambda a, b: a.order - b.order)
        self._material_right_profiles.sort(cmp=lambda a, b: a.order - b.order)

    def getProfileNames(self):
        ret = []
        for profile in self._print_profiles:
            if profile.name not in ret:
                ret.append(profile.name)
        return ret

    def getMaterialLeftNames(self):
        ret = []
        if self._material_in_print_profile:
            for profile in self._print_profiles:
                if profile.material_left is not None and profile.material_left not in ret:
                    ret.append(profile.material_left)
        else:
            for profile in self._material_left_profiles:
                if profile.name not in ret:
                    ret.append(profile.name)
        return ret

    def getMaterialRightNames(self):
        ret = []
        if self._material_in_print_profile:
            for profile in self._print_profiles:
                if profile.material_right is not None and profile.material_right not in ret:
                    ret.append(profile.material_right)
        else:
            for profile in self._material_right_profiles:
                if profile.name not in ret:
                    ret.append(profile.name)
        return ret

    def isValidProfileOption(self, profile_name, material_left, material_right):
        return self._getProfileFor(profile_name, material_left, material_right) is not None

    def getSettingsFor(self, profile_name, material_left, material_right):
        settings = {}

        current_profile = self._getProfileFor(profile_name, material_left, material_right)
        cp = configparser.ConfigParser()
        cp.read(current_profile.filename)
        for setting in profile.settingsList:
            if setting.isProfile():
                if cp.has_option('profile', setting.getName()):
                    settings[setting.getName()] = cp.get('profile', setting.getName())

        if not self._material_in_print_profile:
            for current_profile in self._material_left_profiles:
                if current_profile.name == material_left:
                    cp = configparser.ConfigParser()
                    cp.read(current_profile.filename)
                    for setting in profile.settingsList:
                        if setting.isProfile():
                            if cp.has_option('profile', setting.getName()):
                                settings[setting.getName()] = cp.get('profile', setting.getName())

        if not self._material_in_print_profile:
            for current_profile in self._material_right_profiles:
                if current_profile.name == material_right:
                    cp = configparser.ConfigParser()
                    cp.read(current_profile.filename)
                    for setting in profile.settingsList:
                        if setting.isProfile():
                            if cp.has_option('profile', setting.getName()):
                                settings[setting.getName()] = cp.get('profile', setting.getName())

        return settings

    def _getProfileFor(self, profile_name, material_left, material_right):
        if self._material_in_print_profile:
            for profile in self._print_profiles:
                if profile.name == profile_name and profile.material_left == material_left and material_right == profile.material_right:
                    return profile
        else:
            for profile in self._print_profiles:
                if profile.name == profile_name:
                    return profile
        return None

class IdexPanel(wx.Panel):
    "Main user interface window for Quickprint mode"
    def __init__(self, parent, callback):
        super(IdexPanel, self).__init__(parent)

        self._callback = callback

        self._profile_manager = ProfileManager()

        self._print_profile_options = []
        self._print_material_left_options = []
        self._print_material_right_options = []


        printMaterialLeftPanel = wx.Panel(self)
        for name in self._profile_manager.getMaterialLeftNames():
            button = wx.RadioButton(printMaterialLeftPanel, -1, name, style=wx.RB_GROUP if len(self._print_material_left_options) == 0 else 0)
            button.name = name
            self._print_material_left_options.append(button)
            if profile.getPreference('simpleModeMaterialLeft') == name:
                button.SetValue(True)

        printMaterialRightPanel = wx.Panel(self)
        for name in self._profile_manager.getMaterialRightNames():
            button = wx.RadioButton(printMaterialRightPanel, -1, name, style=wx.RB_GROUP if len(self._print_material_right_options) == 0 else 0)
            button.name = name
            self._print_material_right_options.append(button)
            if profile.getPreference('simpleModeMaterialRight') == name:
                button.SetValue(True)

        printTypePanel = wx.Panel(self)
        for name in self._profile_manager.getProfileNames():
            button = wx.RadioButton(printTypePanel, -1, name, style=wx.RB_GROUP if len(self._print_profile_options) == 0 else 0)
            button.name = name
            self._print_profile_options.append(button)
            if profile.getPreference('simpleModeProfile') == name:
                button.SetValue(True)

        if len(self._print_material_left_options) < 1:
            printMaterialLeftPanel.Show(False)
        if len(self._print_material_right_options) < 1:
            printMaterialRightPanel.Show(False)

        self.printSupport = wx.CheckBox(self, -1, _("Print support structure"))
        self.platform_adhesion_panel = wx.Panel(self)
        self.platform_adhesion_label = wx.StaticText(self.platform_adhesion_panel, -1, _("Platform adhesion"))
        self.platform_adhesion_combo = wx.ComboBox(self.platform_adhesion_panel, -1, '', choices=[_("None"), _("Brim")], style=wx.CB_DROPDOWN|wx.CB_READONLY)
        self.platform_adhesion_combo.SetSelection(int(profile.getPreference('simpleModePlatformAdhesion')))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.platform_adhesion_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 10)
        sizer.Add(self.platform_adhesion_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP, 10)
        self.platform_adhesion_panel.SetSizer(sizer)

        sizer = wx.GridBagSizer()
        sizer.SetEmptyCellSize((0, 0))
        self.SetSizer(sizer)

        sb = wx.StaticBox(printMaterialLeftPanel, label=_("Left Material:"))
        boxsizer = wx.StaticBoxSizer(sb, wx.VERTICAL)
        for button in self._print_material_left_options:
            boxsizer.Add(button)
        printMaterialLeftPanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        printMaterialLeftPanel.GetSizer().Add(boxsizer, flag=wx.EXPAND)
        sizer.Add(printMaterialLeftPanel, (1,0), flag=wx.EXPAND)

        sb = wx.StaticBox(printMaterialRightPanel, label=_(" Right Material:"))
        boxsizer = wx.StaticBoxSizer(sb, wx.VERTICAL)
        for button in self._print_material_right_options:
            boxsizer.Add(button)
        printMaterialRightPanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        printMaterialRightPanel.GetSizer().Add(boxsizer, flag=wx.EXPAND)
        sizer.Add(printMaterialRightPanel, (2,0), flag=wx.EXPAND)

        sb = wx.StaticBox(printTypePanel, label=_("Quality:"))
        boxsizer = wx.StaticBoxSizer(sb, wx.VERTICAL)
        for button in self._print_profile_options:
            boxsizer.Add(button)
        printTypePanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
        printTypePanel.GetSizer().Add(boxsizer, flag=wx.EXPAND)
        sizer.Add(printTypePanel, (0,0), flag=wx.EXPAND)

        sb = wx.StaticBox(self, label=_("Other:"))
        boxsizer = wx.StaticBoxSizer(sb, wx.VERTICAL)
        boxsizer.Add(self.printSupport)
        boxsizer.Add(self.platform_adhesion_panel)
        sizer.Add(boxsizer, (3,0), flag=wx.EXPAND)

        for button in self._print_profile_options:
            button.Bind(wx.EVT_RADIOBUTTON, self._update)
        for button in self._print_material_left_options:
            button.Bind(wx.EVT_RADIOBUTTON, self._update)
        for button in self._print_material_right_options:
            button.Bind(wx.EVT_RADIOBUTTON, self._update)

        self.printSupport.Bind(wx.EVT_CHECKBOX, self._update)
        self.platform_adhesion_combo.Bind(wx.EVT_COMBOBOX, self._update)

        self._update(None)

    def _update(self, e):
        profile_name = self._getActiveProfileName()
        material_left = self._getActiveMaterialLeftName()
        material_right = self._getActiveMaterialRightName()
        if profile_name is None:
            self._print_profile_options[1].SetValue(True)
            profile_name = self._getActiveProfileName()

        if material_left is None:
            if len(self._print_material_left_options) > 0:
                self._print_material_left_options[0].SetValue(True)
                material_left = self._getActiveMaterialLeftName()
            else:
                material_left = ''

        if material_right is None:
            if len(self._print_material_right_options) > 0:
                self._print_material_right_options[0].SetValue(True)
                material_right = self._getActiveMaterialRightName()
            else:
                material_right = ''

        profile.putPreference('simpleModeProfile', profile_name)
        profile.putPreference('simpleModeMaterialLeft', material_left)
        profile.putPreference('simpleModeMaterialRight', material_right)
        profile.putPreference('simpleModePlatformAdhesion', self.platform_adhesion_combo.GetSelection())

        self._updateAvailableOptions()
        self._callback()

    def _getActiveProfileName(self):
        for button in self._print_profile_options:
            if button.GetValue():
                return button.name
        return None

    def _getActiveMaterialLeftName(self):
        for button in self._print_material_left_options:
            if button.GetValue():
                return button.name
        return None

    def _getActiveMaterialRightName(self):
        for button in self._print_material_right_options:
            if button.GetValue():
                return button.name
        return None

    def _updateAvailableOptions(self):
        profile_name = self._getActiveProfileName()
        material_left = self._getActiveMaterialLeftName()
        material_right = self._getActiveMaterialRightName()

        if not self._profile_manager.isValidProfileOption(profile_name, material_left, material_right ):
            for button in self._print_profile_options:
                if self._profile_manager.isValidProfileOption(button.name, material_left, material_right):
                    button.SetValue(True)
                    profile_name = button.name
        if not self._profile_manager.isValidProfileOption(profile_name, material_left, material_right):
            for button in self._print_material_left_options:
                if self._profile_manager.isValidProfileOption(profile_name, button.name, material_right):
                    button.SetValue(True)
                    material_left = button.name
            for button in self._print_material_right_options:
                if self._profile_manager.isValidProfileOption(profile_name, material_left, button.name):
                    button.SetValue(True)
                    material_right = button.name
        if not self._profile_manager.isValidProfileOption(profile_name, material_left, material_right):
            for p_button in self._print_profile_options:
                for ml_button in self._print_material_left_options:
                    for mr_button in self._print_material_left_options:
                        if self._profile_manager.isValidProfileOption(p_button.name, ml_button.name, mr_button.name):
                            ml_button.SetValue(True)
                            mr_button.SetValue(True)
                            p_button.SetValue(True)
                            profile_name = p_button.name
                            material_left = ml_button.name
                            material_right = mr_button.name

        for button in self._print_material_left_options:
            button.Enable(self._profile_manager.isValidProfileOption(profile_name, button.name, material_right))
        for button in self._print_material_right_options:
            button.Enable(self._profile_manager.isValidProfileOption(profile_name, material_left, button.name))
        for button in self._print_profile_options:
            button.Enable(self._profile_manager.isValidProfileOption(button.name, material_left, material_right))

    def getSettingOverrides(self):
        profile_name = self._getActiveProfileName()
        material_name = self._getActiveMaterialLeftName()
        nozzle_name = self._getActiveMaterialRightName()

        settings = {}
        for setting in profile.settingsList:
            if not setting.isProfile():
                continue
            settings[setting.getName()] = setting.getDefault()

        settings.update(self._profile_manager.getSettingsFor(profile_name, material_name, nozzle_name))
        if self.printSupport.GetValue():
            settings['support'] = "Exterior Only"
        else:
            settings['support'] = "None"
        if self.platform_adhesion_combo.GetValue() == _("Brim"):
            settings['platform_adhesion'] = "Brim"
        else:
            settings['platform_adhesion'] = "None"
        return settings

    def updateProfileToControls(self):
        pass
