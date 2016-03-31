__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import wx
import os
import webbrowser
import sys
import ConfigParser as configparser


from Cura.gui import configBase
from Cura.gui import expertConfig
from Cura.gui import alterationPanel
from Cura.gui import pluginPanel
from Cura.gui import preferencesDialog
from Cura.gui import configWizard
from Cura.gui import firmwareInstall
from Cura.gui import simpleMode
from Cura.gui import sceneView
from Cura.gui import aboutWindow
from Cura.gui.util import dropTarget
#from Cura.gui.tools import batchRun
from Cura.gui.tools import pidDebugger
from Cura.gui.tools import minecraftImport
from Cura.util import profile
from Cura.util import version
from Cura.gui import configFirmware
import platform
from Cura.util import meshLoader

try:
    #MacOS release currently lacks some wx components, like the Publisher.
    from wx.lib.pubsub import Publisher
except:
    Publisher = None

class mainWindow(wx.Frame):
    def __init__(self):
        super(mainWindow, self).__init__(None, title='Cura-BCN3D ' + version.getVersion())

        wx.EVT_CLOSE(self, self.OnClose)

        # allow dropping any file, restrict later
        self.SetDropTarget(dropTarget.FileDropTarget(self.OnDropFiles))

        # TODO: wxWidgets 2.9.4 has a bug when NSView does not register for dragged types when wx drop target is set. It was fixed in 2.9.5
        if sys.platform.startswith('darwin'):
            try:
                import objc
                nswindow = objc.objc_object(c_void_p=self.MacGetTopLevelWindowRef())
                view = nswindow.contentView()
                view.registerForDraggedTypes_([u'NSFilenamesPboardType'])
            except:
                pass

        self.normalModeOnlyItems = []

        mruFile = os.path.join(profile.getBasePath(), 'mru_filelist.ini')
        self.config = wx.FileConfig(appName="Cura",
                        localFilename=mruFile,
                        style=wx.CONFIG_USE_LOCAL_FILE)

        self.ID_MRU_MODEL1, self.ID_MRU_MODEL2, self.ID_MRU_MODEL3, self.ID_MRU_MODEL4, self.ID_MRU_MODEL5, self.ID_MRU_MODEL6, self.ID_MRU_MODEL7, self.ID_MRU_MODEL8, self.ID_MRU_MODEL9, self.ID_MRU_MODEL10 = [wx.NewId() for line in xrange(10)]
        self.modelFileHistory = wx.FileHistory(10, self.ID_MRU_MODEL1)
        self.config.SetPath("/ModelMRU")
        self.modelFileHistory.Load(self.config)

        self.ID_MRU_PROFILE1, self.ID_MRU_PROFILE2, self.ID_MRU_PROFILE3, self.ID_MRU_PROFILE4, self.ID_MRU_PROFILE5, self.ID_MRU_PROFILE6, self.ID_MRU_PROFILE7, self.ID_MRU_PROFILE8, self.ID_MRU_PROFILE9, self.ID_MRU_PROFILE10 = [wx.NewId() for line in xrange(10)]
        self.profileFileHistory = wx.FileHistory(10, self.ID_MRU_PROFILE1)
        self.config.SetPath("/ProfileMRU")
        self.profileFileHistory.Load(self.config)

        self.menubar = wx.MenuBar()
        self.fileMenu = wx.Menu()
        i = self.fileMenu.Append(-1, _("Load model file...\tCTRL+L"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.showLoadModel(), i)
        i = self.fileMenu.Append(-1, _("Load Draudi file...\tCTRL+D"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.onLoadDraudiModel(), i)
        i = self.fileMenu.Append(-1, _("Save model...\tCTRL+S"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.showSaveModel(), i)
        i = self.fileMenu.Append(-1, _("Reload platform\tF5"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.reloadScene(e), i)
        i = self.fileMenu.Append(-1, _("Clear platform"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.OnDeleteAll(e), i)

        self.fileMenu.AppendSeparator()
        i = self.fileMenu.Append(-1, _("Print...\tCTRL+P"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.OnPrintButton(1), i)
        i = self.fileMenu.Append(-1, _("Save GCode...\tCTRL+G"))
        self.Bind(wx.EVT_MENU, lambda e: self.scene.showSaveGCode(), i)
        i = self.fileMenu.Append(-1, _("Show slice engine log..."))
        self.Bind(wx.EVT_MENU, lambda e: self.scene._showEngineLog(), i)

        self.fileMenu.AppendSeparator()
        i = self.fileMenu.Append(-1, _("Open Profile...\tCTRL+C"))
        self.normalModeOnlyItems.append(i)
        self.Bind(wx.EVT_MENU, lambda e: self.scene.OnLoadConfigurations(), i)
        i = self.fileMenu.Append(-1, _("Save Profile..."))
        self.normalModeOnlyItems.append(i)
        self.Bind(wx.EVT_MENU, self.OnSaveProfile, i)
        if version.isDevVersion():
            i = self.fileMenu.Append(-1, "Save difference from default...")
            self.normalModeOnlyItems.append(i)
            self.Bind(wx.EVT_MENU, self.OnSaveDifferences, i)
        i = self.fileMenu.Append(-1, _("Load Profile from GCode..."))
        self.normalModeOnlyItems.append(i)
        self.Bind(wx.EVT_MENU, self.OnLoadProfileFromGcode, i)
        self.fileMenu.AppendSeparator()
        i = self.fileMenu.Append(-1, _("Reset Profile to default"))
        self.normalModeOnlyItems.append(i)
        self.Bind(wx.EVT_MENU, self.OnResetProfile, i)

        self.fileMenu.AppendSeparator()
        i = self.fileMenu.Append(-1, _("Preferences...\tCTRL+,"))
        self.Bind(wx.EVT_MENU, self.OnPreferences, i)
        i = self.fileMenu.Append(-1, _("Machine settings..."))
        self.Bind(wx.EVT_MENU, self.OnMachineSettings, i)
        self.fileMenu.AppendSeparator()

        # Model MRU list
        modelHistoryMenu = wx.Menu()
        self.fileMenu.AppendMenu(wx.NewId(), '&' + _("Recent Model Files"), modelHistoryMenu)
        self.modelFileHistory.UseMenu(modelHistoryMenu)
        self.modelFileHistory.AddFilesToMenu()
        self.Bind(wx.EVT_MENU_RANGE, self.OnModelMRU, id=self.ID_MRU_MODEL1, id2=self.ID_MRU_MODEL10)

        # Profle MRU list
        profileHistoryMenu = wx.Menu()
        self.fileMenu.AppendMenu(wx.NewId(), _("Recent Profile Files"), profileHistoryMenu)
        self.profileFileHistory.UseMenu(profileHistoryMenu)
        self.profileFileHistory.AddFilesToMenu()
        self.Bind(wx.EVT_MENU_RANGE, self.OnProfileMRU, id=self.ID_MRU_PROFILE1, id2=self.ID_MRU_PROFILE10)

        self.fileMenu.AppendSeparator()
        i = self.fileMenu.Append(wx.ID_EXIT, _("Quit"))
        self.Bind(wx.EVT_MENU, self.OnQuit, i)
        self.menubar.Append(self.fileMenu, '&' + _("File"))

        toolsMenu = wx.Menu()
        #i = toolsMenu.Append(-1, 'Batch run...')
        #self.Bind(wx.EVT_MENU, self.OnBatchRun, i)
        #self.normalModeOnlyItems.append(i)

        if minecraftImport.hasMinecraft():
            i = toolsMenu.Append(-1, _("Minecraft map import..."))
            self.Bind(wx.EVT_MENU, self.OnMinecraftImport, i)

        if version.isDevVersion():
            i = toolsMenu.Append(-1, _("PID Debugger..."))
            self.Bind(wx.EVT_MENU, self.OnPIDDebugger, i)
            i = toolsMenu.Append(-1, _("Auto Firmware Update..."))
            self.Bind(wx.EVT_MENU, self.OnAutoFirmwareUpdate, i)

        #i = toolsMenu.Append(-1, _("Copy profile to clipboard"))
        #self.Bind(wx.EVT_MENU, self.onCopyProfileClipboard,i)

        toolsMenu.AppendSeparator()
        self.allAtOnceItem = toolsMenu.Append(-1, _("Print all at once"), kind=wx.ITEM_RADIO)
        self.Bind(wx.EVT_MENU, self.onOneAtATimeSwitch, self.allAtOnceItem)
        self.oneAtATime = toolsMenu.Append(-1, _("Print one at a time"), kind=wx.ITEM_RADIO)
        self.Bind(wx.EVT_MENU, self.onOneAtATimeSwitch, self.oneAtATime)
        if profile.getPreference('oneAtATime') == 'True':
            self.oneAtATime.Check(True)
        else:
            self.allAtOnceItem.Check(True)

        self.menubar.Append(toolsMenu, _("Tools"))

        #Machine menu for machine configuration/tooling
        self.machineMenu = wx.Menu()
        self.updateMachineMenu()

        self.menubar.Append(self.machineMenu, _("Machine"))

        expertMenu = wx.Menu()
        i = expertMenu.Append(-1, _("Switch to quickprint..."), kind=wx.ITEM_RADIO)
        self.switchToQuickprintMenuItem = i
        self.Bind(wx.EVT_MENU, self.OnSimpleSwitch, i)

        i = expertMenu.Append(-1, _("Switch to full settings..."), kind=wx.ITEM_RADIO)
        self.switchToNormalMenuItem = i
        self.Bind(wx.EVT_MENU, self.OnNormalSwitch, i)
        expertMenu.AppendSeparator()

        i = expertMenu.Append(-1, _("Open expert settings...\tCTRL+E"))
        self.normalModeOnlyItems.append(i)
        self.Bind(wx.EVT_MENU, self.OnExpertOpen, i)
        expertMenu.AppendSeparator()
        self.bedLevelWizardMenuItem = expertMenu.Append(-1, _("Run bed leveling wizard..."))
        self.Bind(wx.EVT_MENU, self.OnBedLevelWizard, self.bedLevelWizardMenuItem)
        self.headOffsetWizardMenuItem = expertMenu.Append(-1, _("Run head offset wizard..."))
        self.Bind(wx.EVT_MENU, self.OnHeadOffsetWizard, self.headOffsetWizardMenuItem)

        self.menubar.Append(expertMenu, _("Expert"))

        helpMenu = wx.Menu()
        i = helpMenu.Append(-1, _("Online documentation..."))
        self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('http://www.bcn3dtechnologies.com/es/forum'), i)
        if sys.platform.startswith('win'):
            i = helpMenu.Append(-1, _("Report a problem..."))
            self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('https://github.com/BCN3D/BCN3D-Cura-Windows/issues'), i)
        elif sys.platform.startswith('darwin'):
            i = helpMenu.Append(-1, _("Report a problem..."))
            self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('https://github.com/BCN3D/BCN3D-Cura-Mac/issues'), i)
        i = helpMenu.Append(-1, _("Check for update..."))
        self.Bind(wx.EVT_MENU, self.OnCheckForUpdate, i)
        i = helpMenu.Append(-1, _("Open YouMagine website..."))
        self.Bind(wx.EVT_MENU, lambda e: webbrowser.open('https://www.youmagine.com/'), i)
        i = helpMenu.Append(-1, _("About Cura..."))
        self.Bind(wx.EVT_MENU, self.OnAbout, i)
        self.menubar.Append(helpMenu, _("Help"))
        self.SetMenuBar(self.menubar)

        self.splitter = wx.SplitterWindow(self, style = wx.SP_3D | wx.SP_LIVE_UPDATE)
        self.leftPane = wx.Panel(self.splitter, style=wx.BORDER_NONE)
        self.rightPane = wx.Panel(self.splitter, style=wx.BORDER_NONE)
        self.splitter.Bind(wx.EVT_SPLITTER_DCLICK, lambda evt: evt.Veto())

        #Preview window
        self.scene = sceneView.SceneView(self.rightPane)

        ##Gui components##
        self.simpleSettingsPanel = easySettingsPanel(self.leftPane, self.scene.sceneUpdated)
        self.normalSettingsPanel = normalSettingsPanel(self.leftPane, self.scene.sceneUpdated)

        self.leftSizer = wx.BoxSizer(wx.VERTICAL)
        self.leftSizer.Add(self.simpleSettingsPanel, 1, wx.EXPAND)
        self.leftSizer.Add(self.normalSettingsPanel, 1, wx.EXPAND)
        self.leftPane.SetSizer(self.leftSizer)

        #Main sizer, to position the preview window, buttons and tab control
        sizer = wx.BoxSizer()
        self.rightPane.SetSizer(sizer)
        sizer.Add(self.scene, 1, flag=wx.EXPAND)

        # Main window sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)
        sizer.Add(self.splitter, 1, wx.EXPAND)
        sizer.Layout()
        self.sizer = sizer

        self.updateProfileToAllControls()

        self.SetBackgroundColour(self.normalSettingsPanel.GetBackgroundColour())

        self.simpleSettingsPanel.Show(False)
        self.normalSettingsPanel.Show(False)

        # Set default window size & position
        self.SetSize((wx.Display().GetClientArea().GetWidth()/2,wx.Display().GetClientArea().GetHeight()/2))
        self.Centre()

        #Timer set; used to check if profile is on the clipboard
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer)
        #self.timer.Start(1000)
        self.lastTriedClipboard = profile.getProfileString()

        # Restore the window position, size & state from the preferences file
        try:
            if profile.getPreference('window_maximized') == 'True':
                self.Maximize(True)
            else:
                posx = int(profile.getPreference('window_pos_x'))
                posy = int(profile.getPreference('window_pos_y'))
                width = int(profile.getPreference('window_width'))
                height = int(profile.getPreference('window_height'))
                if posx > 0 or posy > 0:
                    self.SetPosition((posx,posy))
                if width > 0 and height > 0:
                    self.SetSize((width,height))

            self.normalSashPos = int(profile.getPreference('window_normal_sash'))
        except:
            self.normalSashPos = 0
            self.Maximize(True)
        if self.normalSashPos < self.normalSettingsPanel.printPanel.GetBestSize()[0] + 5:
            self.normalSashPos = self.normalSettingsPanel.printPanel.GetBestSize()[0] + 5

        self.splitter.SplitVertically(self.leftPane, self.rightPane, self.normalSashPos)

        if wx.Display.GetFromPoint(self.GetPosition()) < 0:
            self.Centre()
        if wx.Display.GetFromPoint((self.GetPositionTuple()[0] + self.GetSizeTuple()[1], self.GetPositionTuple()[1] + self.GetSizeTuple()[1])) < 0:
            self.Centre()
        if wx.Display.GetFromPoint(self.GetPosition()) < 0:
            self.SetSize((800,600))
            self.Centre()

        self.updateSliceMode()
        self.scene.SetFocus()
        self.dialogframe = None
        if Publisher is not None:
            Publisher().subscribe(self.onPluginUpdate, "pluginupdate")

        pluginCount = self.normalSettingsPanel.pluginPanel.GetActivePluginCount()
        if pluginCount == 1:
            self.scene.notification.message("Warning: 1 plugin from the previous session is still active.")

        if pluginCount > 1:
            self.scene.notification.message("Warning: %i plugins from the previous session are still active." % pluginCount)

    def onPluginUpdate(self,msg): #receives commands from the plugin thread
        cmd = str(msg.data).split(";")
        if cmd[0] == "OpenPluginProgressWindow":
            if len(cmd)==1: #no titel received
                cmd.append("Plugin")
            if len(cmd)<3: #no message text received
                cmd.append("Plugin is executed...")
            dialogwidth = 300
            dialogheight = 80
            self.dialogframe = wx.Frame(self, -1, cmd[1],pos = ((wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)-dialogwidth)/2,(wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)-dialogheight)/2), size=(dialogwidth,dialogheight), style = wx.STAY_ON_TOP)
            self.dialogpanel = wx.Panel(self.dialogframe, -1, pos = (0,0), size = (dialogwidth,dialogheight))
            self.dlgtext = wx.StaticText(self.dialogpanel, label = cmd[2], pos = (10,10), size = (280,40))
            self.dlgbar = wx.Gauge(self.dialogpanel,-1, 100, pos = (10,50), size = (280,20), style = wx.GA_HORIZONTAL)
            self.dialogframe.Show()

        elif cmd[0] == "Progress":
            number = int(cmd[1])
            if number <= 100 and self.dialogframe is not None:
                self.dlgbar.SetValue(number)
            else:
                self.dlgbar.SetValue(100)
        elif cmd[0] == "ClosePluginProgressWindow":
            self.dialogframe.Destroy()
            self.dialogframe=None
        else: #assume first token to be the name and second token the percentage
            if len(cmd)>=2:
                number = int(cmd[1])
            else:
                number = 100
            # direct output to Cura progress bar
            self.scene.printButton.setProgressBar(float(number)/100.)
            self.scene.printButton.setBottomText('%s' % (cmd[0]))
            self.scene.QueueRefresh()

    def onTimer(self, e):
        #Check if there is something in the clipboard
        profileString = ""
        try:
            if not wx.TheClipboard.IsOpened():
                if not wx.TheClipboard.Open():
                    return
                do = wx.TextDataObject()
                if wx.TheClipboard.GetData(do):
                    profileString = do.GetText()
                wx.TheClipboard.Close()

                startTag = "CURA_PROFILE_STRING:"
                if startTag in profileString:
                    #print "Found correct syntax on clipboard"
                    profileString = profileString.replace("\n","").strip()
                    profileString = profileString[profileString.find(startTag)+len(startTag):]
                    if profileString != self.lastTriedClipboard:
                        print profileString
                        self.lastTriedClipboard = profileString
                        profile.setProfileFromString(profileString)
                        self.scene.notification.message("Loaded new profile from clipboard.")
                        self.updateProfileToAllControls()
        except:
            print "Unable to read from clipboard"


    def updateSliceMode(self):
        isSimple = profile.getPreference('startMode') == 'Simple'

        self.normalSettingsPanel.Show(not isSimple)
        self.simpleSettingsPanel.Show(isSimple)
        self.leftPane.Layout()

        for i in self.normalModeOnlyItems:
            i.Enable(not isSimple)
        if isSimple:
            self.switchToQuickprintMenuItem.Check()
        else:
            self.switchToNormalMenuItem.Check()

        # Set splitter sash position & size
        if isSimple:
            # Save normal mode sash
            self.normalSashPos = self.splitter.GetSashPosition()

            # Change location of sash to width of quick mode pane
            #(width, height) = self.simpleSettingsPanel.GetSizer().GetSize()
            self.splitter.SetSashPosition(153, True)

            # Disable sash
            self.splitter.SetSashSize(0)
        else:
            self.splitter.SetSashPosition(self.normalSashPos, True)
            # Enabled sash
            self.splitter.SetSashSize(4)
        self.defaultFirmwareInstallMenuItem.Enable(firmwareInstall.getDefaultFirmware() is not None)
        if profile.getMachineSetting('machine_type').startswith('BCN3DSigma'):
            self.bedLevelWizardMenuItem.Enable(False)
            self.headOffsetWizardMenuItem.Enable(False)
        if int(profile.getMachineSetting('extruder_amount')) < 2:
            self.headOffsetWizardMenuItem.Enable(False)
        self.scene.updateProfileToControls()
        self.scene._scene.pushFree()

    def onOneAtATimeSwitch(self, e):
        profile.putPreference('oneAtATime', self.oneAtATime.IsChecked())
        if self.oneAtATime.IsChecked() and profile.getMachineSettingFloat('extruder_head_size_height') < 1:
            wx.MessageBox(_('For "One at a time" printing, you need to have entered the correct head size and gantry height in the machine settings'), _('One at a time warning'), wx.OK | wx.ICON_WARNING)
        self.scene.updateProfileToControls()
        self.scene._scene.pushFree()
        self.scene.sceneUpdated()

    def OnPreferences(self, e):
        prefDialog = preferencesDialog.preferencesDialog(self)
        prefDialog.Centre()
        prefDialog.Show()
        prefDialog.Raise()
        wx.CallAfter(prefDialog.Show)

    def OnMachineSettings(self, e):
        prefDialog = preferencesDialog.machineSettingsDialog(self)
        prefDialog.Centre()
        prefDialog.Show()
        prefDialog.Raise()

    def OnDropFiles(self, files):
        self.scene.loadFiles(files)

    def OnModelMRU(self, e):
        fileNum = e.GetId() - self.ID_MRU_MODEL1
        path = self.modelFileHistory.GetHistoryFile(fileNum)
        # Update Model MRU
        self.modelFileHistory.AddFileToHistory(path)  # move up the list
        self.config.SetPath("/ModelMRU")
        self.modelFileHistory.Save(self.config)
        self.config.Flush()
        # Load Model
        profile.putPreference('lastFile', path)
        filelist = [ path ]
        self.scene.loadFiles(filelist)

    def addToModelMRU(self, file):
        self.modelFileHistory.AddFileToHistory(file)
        self.config.SetPath("/ModelMRU")
        self.modelFileHistory.Save(self.config)
        self.config.Flush()

    def OnProfileMRU(self, e):
        fileNum = e.GetId() - self.ID_MRU_PROFILE1
        path = self.profileFileHistory.GetHistoryFile(fileNum)
        # Update Profile MRU
        self.profileFileHistory.AddFileToHistory(path)  # move up the list
        self.config.SetPath("/ProfileMRU")
        self.profileFileHistory.Save(self.config)
        self.config.Flush()
        # Load Profile
        profile.loadProfile(path)
        self.updateProfileToAllControls()

    def addToProfileMRU(self, file):
        self.profileFileHistory.AddFileToHistory(file)
        self.config.SetPath("/ProfileMRU")
        self.profileFileHistory.Save(self.config)
        self.config.Flush()

    def updateProfileToAllControls(self):
        self.scene.updateProfileToControls()
        self.normalSettingsPanel.updateProfileToControls()
        self.simpleSettingsPanel.updateProfileToControls()

    def reloadSettingPanels(self):
        self.leftSizer.Detach(self.simpleSettingsPanel)
        self.leftSizer.Detach(self.normalSettingsPanel)
        self.simpleSettingsPanel.Destroy()
        self.normalSettingsPanel.Destroy()
        self.simpleSettingsPanel = easySettingsPanel(self.leftPane, lambda : self.scene.sceneUpdated())
        self.normalSettingsPanel = normalSettingsPanel(self.leftPane, lambda : self.scene.sceneUpdated())
        self.leftSizer.Add(self.simpleSettingsPanel, 1, wx.EXPAND)
        self.leftSizer.Add(self.normalSettingsPanel, 1, wx.EXPAND)
        self.updateSliceMode()
        self.updateProfileToAllControls()

    def updateMachineMenu(self):
        #Remove all items so we can rebuild the menu. Inserting items seems to cause crashes, so this is the safest way.
        for item in self.machineMenu.GetMenuItems():
            self.machineMenu.RemoveItem(item)

        #Add a menu item for each machine configuration.
        for n in xrange(0, profile.getMachineCount()):
            i = self.machineMenu.Append(n + 0x1000, profile.getMachineSetting('machine_name', n).title(), kind=wx.ITEM_RADIO)
            if n == int(profile.getPreferenceFloat('active_machine')):
                i.Check(True)
            self.Bind(wx.EVT_MENU, lambda e: self.OnSelectMachine(e.GetId() - 0x1000), i)

        self.machineMenu.AppendSeparator()
        i = self.machineMenu.Append(-1, _("Add new machine..."))
        self.Bind(wx.EVT_MENU, self.OnAddNewMachine, i)
        i = self.machineMenu.Append(-1, _("Machine settings..."))
        self.Bind(wx.EVT_MENU, self.OnMachineSettings, i)

        #Add tools for machines.
        self.machineMenu.AppendSeparator()

        self.defaultFirmwareInstallMenuItem = self.machineMenu.Append(-1, _("Install default firmware..."))
        self.Bind(wx.EVT_MENU, self.OnDefaultMarlinFirmware, self.defaultFirmwareInstallMenuItem)

        i = self.machineMenu.Append(-1, _("Install custom firmware..."))
        self.Bind(wx.EVT_MENU, self.OnCustomFirmware, i)

        self.updateHardwareFirmwareInstallMenu = self.machineMenu.Append(-1, _("Check for firmware updates..."))
        self.Bind(wx.EVT_MENU, self.OnUpdateHardwareFirmware, self.updateHardwareFirmwareInstallMenu)

    def OnLoadProfileFromGcode(self, e):
        dlg=wx.FileDialog(self, _("Select gcode file to load profile from"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        dlg.SetWildcard("gcode files (*%s)|*%s;*%s" % (profile.getGCodeExtension(), profile.getGCodeExtension(), profile.getGCodeExtension()[0:2]))
        if dlg.ShowModal() == wx.ID_OK:
            gcodeFile = dlg.GetPath()
            f = open(gcodeFile, 'r')
            hasProfile = False
            for line in f:
                if line.startswith(';CURA_PROFILE_STRING:'):
                    profile.setProfileFromString(line[line.find(':')+1:].strip())
                    if ';{profile_string}' not in profile.getAlterationFile('end.gcode'):
                        profile.setAlterationFile('end.gcode', profile.getAlterationFile('end.gcode') + '\n;{profile_string}')
                    hasProfile = True
            if hasProfile:
                self.updateProfileToAllControls()
            else:
                wx.MessageBox(_("No profile found in GCode file.\nThis feature only works with GCode files made by Cura 12.07 or newer."), _("Profile load error"), wx.OK | wx.ICON_INFORMATION)
        dlg.Destroy()

    def OnSaveProfile(self, e):
        dlg=wx.FileDialog(self, _("Select profile file to save"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_SAVE)
        dlg.SetWildcard("ini files (*.ini)|*.ini")
        if dlg.ShowModal() == wx.ID_OK:
            profile_filename = dlg.GetPath()
            if not profile_filename.lower().endswith('.ini'): #hack for linux, as for some reason the .ini is not appended.
                profile_filename += '.ini'
            profile.saveProfile(profile_filename)
        dlg.Destroy()

    def OnSaveDifferences(self, e):
        dlg=wx.FileDialog(self, _("Select profile file to save"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_SAVE)
        dlg.SetWildcard("ini files (*.ini)|*.ini")
        if dlg.ShowModal() == wx.ID_OK:
            profile_filename = dlg.GetPath()
            if not profile_filename.lower().endswith('.ini'): #hack for linux, as for some reason the .ini is not appended.
                profile_filename += '.ini'
            profile.saveProfileDifferenceFromDefault(profile_filename)
        dlg.Destroy()

    def OnResetProfile(self, e):
        dlg = wx.MessageDialog(self, _("This will reset all profile settings to defaults.\nUnless you have saved your current profile, all settings will be lost!\nDo you really want to reset?"), _("Profile reset"), wx.YES_NO | wx.ICON_QUESTION)
        result = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if result:
            profile.resetProfile()
            self.updateProfileToAllControls()

    def OnSimpleSwitch(self, e):
        profile.putPreference('startMode', 'Simple')
        self.updateSliceMode()

    def OnNormalSwitch(self, e):
        profile.putPreference('startMode', 'Normal')
        dlg = wx.MessageDialog(self, _("Copy the settings from quickprint to your full settings?\n(This will overwrite any full setting modifications you have)"), _("Profile copy"), wx.YES_NO | wx.ICON_QUESTION)
        result = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        #if result:
            #profile.resetProfile()
            #for k, v in self.simpleSettingsPanel.getSettingOverrides:
                #profile.putProfileSetting(k, v)
        self.updateProfileToAllControls()
        self.updateSliceMode()

    def OnDefaultMarlinFirmware(self, e):
        firmwareInstall.InstallFirmware(self)

    def OnCustomFirmware(self, e):
        if profile.getMachineSetting('machine_type').startswith('ultimaker'):
            wx.MessageBox(_("Warning: Installing a custom firmware does not guarantee that you machine will function correctly, and could damage your machine."), _("Firmware update"), wx.OK | wx.ICON_EXCLAMATION)
        dlg=wx.FileDialog(self, _("Open firmware to upload"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        dlg.SetWildcard("HEX file (*.hex)|*.hex;*.HEX")
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            dlg.Destroy()
            if not(os.path.exists(filename)):
                return
            #For some reason my Ubuntu 10.10 crashes here.
            firmwareInstall.InstallFirmware(self, filename)


    def OnUpdateHardwareFirmware(self, e):
        configFirmware.ConfigFirmware()

    def OnAddNewMachine(self, e):
        self.Hide()
        configWizard.ConfigWizard(True)
        self.Show()
        self.reloadSettingPanels()
        self.updateMachineMenu()

    def OnSelectMachine(self, index):
        profile.setActiveMachine(index)
        self.reloadSettingPanels()

    def OnBedLevelWizard(self, e):
        configWizard.bedLevelWizard()

    def OnHeadOffsetWizard(self, e):
        configWizard.headOffsetWizard()

    def OnExpertOpen(self, e):
        ecw = expertConfig.expertConfigWindow(lambda : self.scene.sceneUpdated())
        ecw.Centre()
        ecw.Show()

    def OnMinecraftImport(self, e):
        mi = minecraftImport.minecraftImportWindow(self)
        mi.Centre()
        mi.Show(True)

    def OnPIDDebugger(self, e):
        debugger = pidDebugger.debuggerWindow(self)
        debugger.Centre()
        debugger.Show(True)

    def OnAutoFirmwareUpdate(self, e):
        dlg=wx.FileDialog(self, _("Open firmware to upload"), os.path.split(profile.getPreference('lastFile'))[0], style=wx.FD_OPEN|wx.FD_FILE_MUST_EXIST)
        dlg.SetWildcard("HEX file (*.hex)|*.hex;*.HEX")
        if dlg.ShowModal() == wx.ID_OK:
            filename = dlg.GetPath()
            dlg.Destroy()
            if not(os.path.exists(filename)):
                return
            #For some reason my Ubuntu 10.10 crashes here.
            installer = firmwareInstall.AutoUpdateFirmware(self, filename)

    def onCopyProfileClipboard(self, e):
        try:
            if not wx.TheClipboard.IsOpened():
                wx.TheClipboard.Open()
                clipData = wx.TextDataObject()
                self.lastTriedClipboard = profile.getProfileString()
                profileString = profile.insertNewlines("CURA_PROFILE_STRING:" + self.lastTriedClipboard)
                clipData.SetText(profileString)
                wx.TheClipboard.SetData(clipData)
                wx.TheClipboard.Close()
        except:
            print "Could not write to clipboard, unable to get ownership. Another program is using the clipboard."

    def OnCheckForUpdate(self, e):
        newVersion = version.checkForNewVersion()
        if newVersion is not None:
            if wx.MessageBox(_("A new version of Cura is available, would you like to download?"), _("New version available"), wx.YES_NO | wx.ICON_INFORMATION) == wx.YES:
                webbrowser.open(newVersion)
        elif newVersion is None:
            wx.MessageBox(_("You are running the latest version of Cura!"), _("Awesome!"), wx.ICON_INFORMATION)

    def OnAbout(self, e):
        aboutBox = aboutWindow.aboutWindow()
        aboutBox.Centre()
        aboutBox.Show()

    def OnClose(self, e):
        profile.saveProfile(profile.getDefaultProfilePath(), True)

        # Save the window position, size & state from the preferences file
        profile.putPreference('window_maximized', self.IsMaximized())
        if not self.IsMaximized() and not self.IsIconized():
            (posx, posy) = self.GetPosition()
            profile.putPreference('window_pos_x', posx)
            profile.putPreference('window_pos_y', posy)
            (width, height) = self.GetSize()
            profile.putPreference('window_width', width)
            profile.putPreference('window_height', height)

            # Save normal sash position.  If in normal mode (!simple mode), get last position of sash before saving it...
            isSimple = profile.getPreference('startMode') == 'Simple'
            if not isSimple:
                self.normalSashPos = self.splitter.GetSashPosition()
            profile.putPreference('window_normal_sash', self.normalSashPos)

        #HACK: Set the paint function of the glCanvas to nothing so it won't keep refreshing. Which can keep wxWidgets from quiting.
        print "Closing down"
        self.scene.OnPaint = lambda e : e
        self.scene._engine.cleanup()
        self.Destroy()

    def OnQuit(self, e):
        self.Close()

class normalSettingsPanel(configBase.configPanelBase):
    "Main user interface window"
    def __init__(self, parent, callback = None):
        super(normalSettingsPanel, self).__init__(parent, callback)

        #Main tabs
        self.nb = wx.Notebook(self)
        self.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
        self.GetSizer().Add(self.nb, 1, wx.EXPAND)

        (left, right, self.printPanel) = self.CreateDynamicConfigTab(self.nb, _('Basic'))
        self._addSettingsToPanels('basic', left, right)
        self.SizeLabelWidths(left, right)

        (left, right, self.advancedPanel) = self.CreateDynamicConfigTab(self.nb, _('Advanced'))
        self._addSettingsToPanels('advanced', left, right)
        self.SizeLabelWidths(left, right)

        #Plugin page
        self.pluginPanel = pluginPanel.pluginPanel(self.nb, callback)
        self.nb.AddPage(self.pluginPanel, _("Plugins"))

        #Alteration page
        if profile.getMachineSetting('gcode_flavor') == 'UltiGCode':
            self.alterationPanel = None
        else:
            self.alterationPanel = alterationPanel.alterationPanel(self.nb, callback)
            self.nb.AddPage(self.alterationPanel, "Start/End-GCode")

        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.nb.SetSize(self.GetSize())
        self.UpdateSize(self.printPanel)
        self.UpdateSize(self.advancedPanel)

    def _addSettingsToPanels(self, category, left, right):
        count = len(profile.getSubCategoriesFor(category)) + len(profile.getSettingsForCategory(category))

        p = left
        n = 0
        for title in profile.getSubCategoriesFor(category):
            n += 1 + len(profile.getSettingsForCategory(category, title))
            if n > count / 2:
                p = right
            configBase.TitleRow(p, _(title))
            for s in profile.getSettingsForCategory(category, title):
                configBase.SettingRow(p, s.getName())

    def SizeLabelWidths(self, left, right):
        leftWidth = self.getLabelColumnWidth(left)
        rightWidth = self.getLabelColumnWidth(right)
        maxWidth = max(leftWidth, rightWidth)
        self.setLabelColumnWidth(left, maxWidth)
        self.setLabelColumnWidth(right, maxWidth)

    def OnSize(self, e):
        # Make the size of the Notebook control the same size as this control
        self.nb.SetSize(self.GetSize())

        # Propegate the OnSize() event (just in case)
        e.Skip()

        # Perform out resize magic
        self.UpdateSize(self.printPanel)
        self.UpdateSize(self.advancedPanel)

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
                #sizer.Layout()
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
                #sizer.Layout()
                configPanel.Layout()
                self.Layout()
                configPanel.Thaw()

    def updateProfileToControls(self):
        super(normalSettingsPanel, self).updateProfileToControls()
        if self.alterationPanel is not None:
            self.alterationPanel.updateProfileToControls()
        self.pluginPanel.updateProfileToControls()


class easySettingsPanel(configBase.configPanelBase):
    "Main user interface window"
    def __init__(self, parent, callback = None):
        super(easySettingsPanel, self).__init__(parent, callback)

        #Main tabs
        self.nb = wx.Notebook(self)
        self.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
        self.GetSizer().Add(self.nb, 1, wx.EXPAND)

        (left, right, self.mexPanel) = self.CreateDynamicConfigTab(self.nb, _('MEX'))
        self._addSettingsToPanels('single', left, right)
        self.SizeLabelWidths(left, right)

        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            (left, right, self.idexPanel) = self.CreateDynamicConfigTab(self.nb, _('IDEX'))
            self._addSettingsToPanels('dual', left, right)

        self.SizeLabelWidths(left, right)

        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.nb.SetSize(self.GetSize())
        self.UpdateSize(self.mexPanel)
        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            self.UpdateSize(self.idexPanel)


    def _addSettingsToPanels(self, category, left, right):
        count = len(profile.getSubCategoriesFor(category)) + len(profile.getSettingsForCategory(category))

        p = left
        n = 0
        for title in profile.getSubCategoriesFor(category):
            n += 1 + len(profile.getSettingsForCategory(category, title))
            if n > count / 2:
                p = right
            configBase.TitleRow(p, _(title))
            for s in profile.getSettingsForCategory(category, title):
                configBase.SettingRow(p, s.getName())

    def SizeLabelWidths(self, left, right):
        leftWidth = self.getLabelColumnWidth(left)
        rightWidth = self.getLabelColumnWidth(right)
        maxWidth = max(leftWidth, rightWidth)
        self.setLabelColumnWidth(left, maxWidth)
        self.setLabelColumnWidth(right, maxWidth)

    def OnSize(self, e):
        # Make the size of the Notebook control the same size as this control
        self.nb.SetSize(self.GetSize())

        # Propegate the OnSize() event (just in case)
        e.Skip()

        # Perform out resize magic
        self.UpdateSize(self.mexPanel)
        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            self.UpdateSize(self.idexPanel)

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
                #sizer.Layout()
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
                #sizer.Layout()
                configPanel.Layout()
                self.Layout()
                configPanel.Thaw()

    def getSettingOverrides(self):
        settings = {}
        for setting in profile.settingsList:
            if not setting.isProfile():
                continue
            settings[setting.getName()] = setting.getDefault()


        beggining = ';Sliced at: {day} {date} {time}\n;Basic settings: Layer height: {layer_height} Walls: {wall_thickness} Fill: {fill_density}\n' \
                    ';Print time: {print_time}\n;Filament used: {filament_amount}m {filament_weight}g\n;Filament cost: {filament_cost}\n' \
                    ';M190 S{print_bed_temperature}  ;Uncomment to add your own bed temperature line\n;M109 S{print_temperature} ;Uncomment to add your own temperature line\n' \
                    'G21        ;metric values\nG90        ;absolute positioning\nM82        ;set extruder to absolute mode\n' \
                    'M107       ;start with the fan off\nG28 X0 Y0  ;move X/Y to min endstops\nG28 Z0     ;move Z to min endstops\n' \
                    'G1 Z15.0 F{travel_speed} ;move the platform down 15mm\nG92 E0                  ;zero the extruded length\n' \
                    'G1 F200 E3              ;extrude 3mm of feed stock\nG92 E0                  ;zero the extruded length again\n' \
                    'G1 F{travel_speed}\n;Put printing message on LCD screen\nM117 Printing...\n'

        beggining2 = ';Sliced at: {day} {date} {time}\n;Basic settings: Layer height: {layer_height} Walls: {wall_thickness} Fill: {fill_density}\n' \
                     ';Print time: {print_time}\n;Filament used: {filament_amount}m {filament_weight}g\n;Filament cost: {filament_cost}\n' \
                     ';M190 S{print_bed_temperature} ;Uncomment to add your own bed temperature line\n;M104 S{print_temperature} ;Uncomment to add your own temperature line\n' \
                     ';M109 T1 S{print_temperature2} ;Uncomment to add your own temperature line\n;M109 T0 S{print_temperature} ;Uncomment to add your own temperature line\n' \
                     'G21        ;metric values\nG90        ;absolute positioning\nM107       ;start with the fan off\nG28 X0 Y0  ;move X/Y to min endstops\n' \
                     'G28 Z0     ;move Z to min endstops\nG1 Z15.0 F{travel_speed} ;move the platform down 15mm\nT1                      ;Switch to the 2nd extruder\n' \
                     'G92 E0                  ;zero the extruded length\nG1 F200 E10             ;extrude 10mm of feed stock\nG92 E0                  ;zero the extruded length again\n' \
                     'G1 F200 E-{retraction_dual_amount}\nT0                      ;Switch to the first extruder\nG92 E0                  ;zero the extruded length\n' \
                     'G1 F200 E10             ;extrude 10mm of feed stock\nG92 E0                  ;zero the extruded length again\nG1 Z5 F200\nG1 F{travel_speed}\n' \
                     ';Put printing message on LCD screen\nM117 Printing...\n'

        end = 'M104 T0 S0                     ;extruder heater off\nM104 T1 S0                     ;extruder heater off\n' \
              'M140 S0                     ;heated bed heater off (if you have it)\nG91                                    ;relative positioning\n' \
              'G1 E-1 F300                            ;retract the filament a bit before lifting the nozzle, to release some of the pressure\n' \
              'G1 Z+0.5 E-5 X-20 Y-20 F{travel_speed} ;move Z up a bit and retract filament even more\n' \
              'G28 X0 Y0                              ;move X/Y to min endstops, so the head is out of the way\nM84                         ;steppers off\n' \
              'G90                         ;absolute positioning\n;{profile_string}\n'

        end2 = 'M104 S0                     ;extruder heater off\nM140 S0                     ;heated bed heater off (if you have it)\n' \
               'G91                                    ;relative positioning\n' \
               'G1 E-1 F300                            ;retract the filament a bit before lifting the nozzle, to release some of the pressure\n' \
               'G1 Z+0.5 E-5 X-20 Y-20 F{travel_speed} ;move Z up a bit and retract filament even more\n' \
               'G28 X0 Y0                              ;move X/Y to min endstops, so the head is out of the way\n' \
               'M84                         ;steppers off\nG90                         ;absolute positioning\n;{profile_string}\n'

        #We have a check for BCN3D Sigma because we also need to take care of both plus and r
        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            #We first check for the options that could happen under quality fast
            if profile.getProfileSetting('quality_fast') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality fast
                settings['layer_height'] = 0.3
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 60
                settings['infill_speed'] = 120
                settings['solidarea_speed'] = 80
                settings['inset0_speed'] = 60
                settings['insetx_speed'] = 80
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM104 T1 S25\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM104 T1 S25\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM104 T1 S25\nM190 S100\nT0\n' + beggining
                #Then we check the option for the right extruder and the materials
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T1 S220\nM104 T0 S25\nM190 S45\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T1 S250\nM104 T0 S25\nM190 S70\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T1 S250\nM104 T0 S25\nM190 S100\nT1\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end
            #Second we check all the options for standard quality
            elif profile.getProfileSetting('quality_standard') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality standard
                settings['layer_height'] = 0.2
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 40
                settings['infill_speed'] = 60
                settings['solidarea_speed'] = 40
                settings['inset0_speed'] = 40
                settings['insetx_speed'] = 50
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM104 T1 S25\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM104 T1 S25\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM104 T1 S25\nM190 S100\nT0\n' + beggining
                #Then we check the option for the right extruder and the materials
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T1 S220\nM104 T0 S25\nM190 S45\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T1 S250\nM104 T0 S25\nM190 S70\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T1 S250\nM104 T0 S25\nM190 S100\nT1\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end
            #Third we check all the options for high quality
            elif profile.getProfileSetting('quality_high') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality high
                settings['layer_height'] = 0.1
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 35
                settings['infill_speed'] = 50
                settings['solidarea_speed'] = 35
                settings['inset0_speed'] = 30
                settings['insetx_speed'] = 40
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM104 T1 S25\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM104 T1 S25\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM104 T1 S25\nM190 S100\nT0\n' + beggining
                #Then we check the option for the right extruder and the materials
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T1 S220\nM104 T0 S25\nM190 S45\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T1 S250\nM104 T0 S25\nM190 S70\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T1 S250\nM104 T0 S25\nM190 S100\nT1\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end
            #Fourth, we check all the options for strong quality
            elif profile.getProfileSetting('quality_strong') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality strong
                settings['layer_height'] = 0.2
                settings['wall_thickness'] = 1.6
                settings['fill_density'] = 30
                settings['bottom_layer_speed'] = 35
                settings['infill_speed'] = 60
                settings['solidarea_speed'] = 35
                settings['inset0_speed'] = 30
                settings['insetx_speed'] = 40
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM104 T1 S25\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM104 T1 S25\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM104 T1 S25\nM190 S100\nT0\n' + beggining
                #Then we check the option for the right extruder and the materials
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T1 S220\nM104 T0 S25\nM190 S45\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T1 S250\nM104 T0 S25\nM190 S70\nT1\n' + beggining
                elif profile.getProfileSetting('extruder_right') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T1 S250\nM104 T0 S25\nM190 S100\nT1\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end
            #Now we have the idex options
            #Quality fast and dual
            elif profile.getProfileSetting('quality_fast_dual') == 'True':
                settings['layer_height'] = 0.3
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 60
                settings['infill_speed'] = 120
                settings['solidarea_speed'] = 80
                settings['inset0_speed'] = 60
                settings['insetx_speed'] = 80
                #First we check with the left extruder and pla and all the other options on the right
                if profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM104 T1 S220\nM109 T0 S220\nM190 S45\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S220\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S220\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S55\nM104 T1 S190\nM109 T0 S220\nM190 S55\nT0\n' + beggining2
                #Now we check for the left extruder with abs and all the other option on the right
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S220\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S190\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                #Now we check for the left extruder with filaflex and all the other option on the right
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S190\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                #Now we want to check for the case in which we have supports on the right extruder
                if profile.getProfileSetting('dual_support') == 'True':
                    settings['support'] = 'Exterior Only'
                    settings['support_dual_extrusion'] = 'Second extruder'
                #Add custom end.gcode
                settings['end.gcode'] = end
            #Quality standard and dual
            elif profile.getProfileSetting('quality_standard_dual') == 'True':
                settings['layer_height'] = 0.2
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 40
                settings['infill_speed'] = 60
                settings['solidarea_speed'] = 40
                settings['inset0_speed'] = 40
                settings['insetx_speed'] = 50
                #First we check with the left extruder and pla and all the other options on the right
                if profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM104 T1 S220\nM109 T0 S220\nM190 S45\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S220\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S220\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S55\nM104 T1 S190\nM109 T0 S220\nM190 S55\nT0\n' + beggining2
                #Now we check for the left extruder with abs and all the other option on the right
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S220\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S190\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                #Now we check for the left extruder with filaflex and all the other option on the right
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S190\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                #Now we want to check for the case in which we have supports on the right extruder
                if profile.getProfileSetting('dual_support') == 'True':
                    settings['support'] = 'Exterior Only'
                    settings['support_dual_extrusion'] = 'Second extruder'
                #Add custom end.gcode
                settings['end.gcode'] = end
            #Quality high and dual
            elif profile.getProfileSetting('quality_high_dual') == 'True':
                settings['layer_height'] = 0.1
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 35
                settings['infill_speed'] = 50
                settings['solidarea_speed'] = 35
                settings['inset0_speed'] = 30
                settings['insetx_speed'] = 40
                #First we check with the left extruder and pla and all the other options on the right
                if profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM104 T1 S220\nM109 T0 S220\nM190 S45\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S220\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S220\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S55\nM104 T1 S190\nM109 T0 S220\nM190 S55\nT0\n' + beggining2
                #Now we check for the left extruder with abs and all the other option on the right
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S220\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S190\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                #Now we check for the left extruder with filaflex and all the other option on the right
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S190\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                #Now we want to check for the case in which we have supports on the right extruder
                if profile.getProfileSetting('dual_support') == 'True':
                    settings['support'] = 'Exterior Only'
                    settings['support_dual_extrusion'] = 'Second extruder'
                #Add custom end.gcode
                settings['end.gcode'] = end
            #Quality strong and dual
            elif profile.getProfileSetting('quality_strong_dual') == 'True':
                settings['layer_height'] = 0.2
                settings['wall_thickness'] = 1.6
                settings['fill_density'] = 30
                settings['bottom_layer_speed'] = 35
                settings['infill_speed'] = 60
                settings['solidarea_speed'] = 35
                settings['inset0_speed'] = 30
                settings['insetx_speed'] = 40
                #First we check with the left extruder and pla and all the other options on the right
                if profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM104 T1 S220\nM109 T0 S220\nM190 S45\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S220\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S220\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('pla_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S55\nM104 T1 S190\nM109 T0 S220\nM190 S55\nT0\n' + beggining2
                #Now we check for the left extruder with abs and all the other option on the right
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S220\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S250\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('abs_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM104 T1 S190\nM109 T0 S250\nM190 S70\nT0\n' + beggining2
                #Now we check for the left extruder with filaflex and all the other option on the right
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pla_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S220\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('abs_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('fila_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S250\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                elif profile.getProfileSetting('fila_left_dual') == 'True' and profile.getProfileSetting('pva_right_dual') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM104 T1 S190\nM109 T0 S250\nM190 S100\nT0\n' + beggining2
                #Now we want to check for the case in which we have supports on the right extruder
                if profile.getProfileSetting('dual_support') == 'True':
                    settings['support'] = 'Exterior Only'
                    settings['support_dual_extrusion'] = 'Second extruder'
                #Add custom end.gcode
                settings['end.gcode'] = end
        #We have a check for BCN3D Plus
        elif profile.getMachineSetting('machine_type') == 'BCN3DPlus' or profile.getMachineSetting('machine_type') == 'BCN3DR':
            #We first check for the options that could happen under quality fast
            if profile.getProfileSetting('quality_fast') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality fast
                settings['layer_height'] = 0.3
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 60
                settings['infill_speed'] = 100
                settings['solidarea_speed'] = 70
                settings['inset0_speed'] = 60
                settings['insetx_speed'] = 80
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM190 S100\nT0\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end2
            #Second we check all the options for standard quality
            elif profile.getProfileSetting('quality_standard') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality standard
                settings['layer_height'] = 0.2
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 40
                settings['infill_speed'] = 60
                settings['solidarea_speed'] = 40
                settings['inset0_speed'] = 40
                settings['insetx_speed'] = 50
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM190 S100\nT0\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end2
            #Third we check all the options for high quality
            elif profile.getProfileSetting('quality_high') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality high
                settings['layer_height'] = 0.1
                settings['wall_thickness'] = 0.8
                settings['fill_density'] = 15
                settings['bottom_layer_speed'] = 30
                settings['infill_speed'] = 50
                settings['solidarea_speed'] = 35
                settings['inset0_speed'] = 30
                settings['insetx_speed'] = 40
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM190 S100\nT0\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end2
            #Fourth, we check all the options for strong quality
            elif profile.getProfileSetting('quality_strong') == 'True':
                #We want to make sure that it is only set to one extruder, so just in case we do the following
                settings['extruder_amount'] = 1
                #Now we just add all the settings that are related to quality strong
                settings['layer_height'] = 0.2
                settings['wall_thickness'] = 1.6
                settings['fill_density'] = 30
                settings['bottom_layer_speed'] = 40
                settings['infill_speed'] = 60
                settings['solidarea_speed'] = 40
                settings['inset0_speed'] = 40
                settings['insetx_speed'] = 50
                #First we check all the options for the left extruder and the materials
                if profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_pla') == 'True':
                    settings['start.gcode'] = 'M140 S45\nM109 T0 S220\nM190 S45\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_abs') == 'True':
                    settings['start.gcode'] = 'M140 S70\nM109 T0 S250\nM190 S70\nT0\n' + beggining
                elif profile.getProfileSetting('extruder_left') == 'True' and profile.getProfileSetting('material_fila') == 'True':
                    settings['start.gcode'] = 'M140 S100\nM109 T0 S250\nM190 S100\nT0\n' + beggining
                #Custom end.gcode
                settings['end.gcode'] = end2

        return settings

    def updateProfileToControls(self):
        super(easySettingsPanel, self).updateProfileToControls()

