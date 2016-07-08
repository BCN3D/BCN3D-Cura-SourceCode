__author__ = 'rmelbourne'

import os
import webbrowser
import threading
import time
import math
import wx
import sys
import time
import serial
import subprocess
import glob

import wx
import wx.wizard

from Cura.gui import firmwareInstall
from Cura.gui import printWindow
from Cura.util import gcodeGenerator
from Cura.util import resources
from Cura.avr_isp import stk500v2
from Cura.avr_isp import ispBase
from Cura.avr_isp import intelHex

from Cura.gui.util import taskbar
from Cura.util import machineCom
from Cura.util import profile
from Cura.util import version
from Cura.util import resources
from Cura.gui import app
from Tkinter import *


class InfoBox(wx.Panel):
    def __init__(self, parent):
        super(InfoBox, self).__init__(parent)
        self.SetBackgroundColour('#FFFF80')

        self.sizer = wx.GridBagSizer(5, 5)
        self.SetSizer(self.sizer)

        self.attentionBitmap = wx.Bitmap(resources.getPathForImage('attention.png'))
        self.errorBitmap = wx.Bitmap(resources.getPathForImage('error.png'))
        self.readyBitmap = wx.Bitmap(resources.getPathForImage('ready.png'))
        self.busyBitmap = [
            wx.Bitmap(resources.getPathForImage('busy-0.png')),
            wx.Bitmap(resources.getPathForImage('busy-1.png')),
            wx.Bitmap(resources.getPathForImage('busy-2.png')),
            wx.Bitmap(resources.getPathForImage('busy-3.png'))
        ]

        self.bitmap = wx.StaticBitmap(self, -1, wx.EmptyBitmapRGBA(24, 24, red=255, green=255, blue=255, alpha=1))
        self.text = wx.StaticText(self, -1, '')
        self.extraInfoButton = wx.Button(self, -1, 'i', style=wx.BU_EXACTFIT)
        self.sizer.Add(self.bitmap, pos=(0, 0), flag=wx.ALL, border=5)
        self.sizer.Add(self.text, pos=(0, 1), flag=wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border=5)
        self.sizer.Add(self.extraInfoButton, pos=(0,2), flag=wx.ALL|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, border=5)
        self.sizer.AddGrowableCol(1)

        self.extraInfoButton.Show(False)

        self.extraInfoUrl = ''
        self.busyState = None
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.doBusyUpdate, self.timer)
        self.Bind(wx.EVT_BUTTON, self.doExtraInfo, self.extraInfoButton)
        self.timer.Start(100)

    def SetInfo(self, info):
        self.SetBackgroundColour('#FFFF80')
        self.text.SetLabel(info)
        self.extraInfoButton.Show(False)
        self.Refresh()

    def SetError(self, info, extraInfoUrl):
        self.extraInfoUrl = extraInfoUrl
        self.SetBackgroundColour('#FF8080')
        self.text.SetLabel(info)
        self.extraInfoButton.Show(True)
        self.Layout()
        self.SetErrorIndicator()
        self.Refresh()

    def SetAttention(self, info):
        self.SetBackgroundColour('#FFFF80')
        self.text.SetLabel(info)
        self.extraInfoButton.Show(False)
        self.SetAttentionIndicator()
        self.Layout()
        self.Refresh()

    def SetBusy(self, info):
        self.SetInfo(info)
        self.SetBusyIndicator()

    def SetBusyIndicator(self):
        self.busyState = 0
        self.bitmap.SetBitmap(self.busyBitmap[self.busyState])

    def doExtraInfo(self, e):
        webbrowser.open(self.extraInfoUrl)

    def doBusyUpdate(self, e):
        if self.busyState is None:
            return
        self.busyState += 1
        if self.busyState >= len(self.busyBitmap):
            self.busyState = 0
        self.bitmap.SetBitmap(self.busyBitmap[self.busyState])

    def SetReadyIndicator(self):
        self.busyState = None
        self.bitmap.SetBitmap(self.readyBitmap)

    def SetErrorIndicator(self):
        self.busyState = None
        self.bitmap.SetBitmap(self.errorBitmap)

    def SetAttentionIndicator(self):
        self.busyState = None
        self.bitmap.SetBitmap(self.attentionBitmap)


class InfoPage(wx.wizard.WizardPageSimple):
    def __init__(self, parent, title):
        wx.wizard.WizardPageSimple.__init__(self, parent)

        sizer = wx.GridBagSizer(5, 5)
        self.sizer = sizer
        self.SetSizer(sizer)

        title = wx.StaticText(self, -1, title)
        title.SetFont(wx.Font(18, wx.SWISS, wx.NORMAL, wx.BOLD))
        sizer.Add(title, pos=(0, 0), span=(1, 2), flag=wx.ALIGN_CENTRE | wx.ALL)
        sizer.Add(wx.StaticLine(self, -1), pos=(1, 0), span=(1, 2), flag=wx.EXPAND | wx.ALL)
        sizer.AddGrowableCol(1)

        self.rowNr = 2

    def AddText(self, info):
        text = wx.StaticText(self, -1, info)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT | wx.RIGHT)
        self.rowNr += 1
        return text

    def AddSeperator(self):
        self.GetSizer().Add(wx.StaticLine(self, -1), pos=(self.rowNr, 0), span=(1, 2), flag=wx.EXPAND | wx.ALL)
        self.rowNr += 1

    def AddHiddenSeperator(self):
        self.AddText("")

    def AddInfoBox(self):
        infoBox = InfoBox(self)
        self.GetSizer().Add(infoBox, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.rowNr += 1
        return infoBox

    def AddRadioButton(self, label, style=0):
        radio = wx.RadioButton(self, -1, label, style=style)
        self.GetSizer().Add(radio, pos=(self.rowNr, 0), span=(1, 2), flag=wx.EXPAND | wx.ALL)
        self.rowNr += 1
        return radio

    def AddCheckbox(self, label, checked=False):
        check = wx.CheckBox(self, -1)
        text = wx.StaticText(self, -1, label)
        check.SetValue(checked)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.GetSizer().Add(check, pos=(self.rowNr, 1), span=(1, 2), flag=wx.ALL)
        self.rowNr += 1
        return check

    def AddButton(self, label):
        button = wx.Button(self, -1, label)
        self.GetSizer().Add(button, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT)
        self.rowNr += 1
        return button

    def AddDualButton(self, label1, label2):
        button1 = wx.Button(self, -1, label1)
        self.GetSizer().Add(button1, pos=(self.rowNr, 0), flag=wx.RIGHT)
        button2 = wx.Button(self, -1, label2)
        self.GetSizer().Add(button2, pos=(self.rowNr, 1))
        self.rowNr += 1
        return button1, button2

    def AddTextCtrl(self, value):
        ret = wx.TextCtrl(self, -1, value)
        self.GetSizer().Add(ret, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT)
        self.rowNr += 1
        return ret

    def AddLabelTextCtrl(self, info, value):
        text = wx.StaticText(self, -1, info)
        ret = wx.TextCtrl(self, -1, value)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT)
        self.GetSizer().Add(ret, pos=(self.rowNr, 1), span=(1, 1), flag=wx.LEFT)
        self.rowNr += 1
        return ret

    def AddTextCtrlButton(self, value, buttonText):
        text = wx.TextCtrl(self, -1, value)
        button = wx.Button(self, -1, buttonText)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT)
        self.GetSizer().Add(button, pos=(self.rowNr, 1), span=(1, 1), flag=wx.LEFT)
        self.rowNr += 1
        return text, button

    def AddBitmap(self, bitmap):
        bitmap = wx.StaticBitmap(self, -1, bitmap)
        self.GetSizer().Add(bitmap, pos=(self.rowNr, 0), span=(1, 2), flag=wx.LEFT | wx.RIGHT)
        self.rowNr += 1
        return bitmap

    def AddCheckmark(self, label, bitmap):
        check = wx.StaticBitmap(self, -1, bitmap)
        text = wx.StaticText(self, -1, label)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.GetSizer().Add(check, pos=(self.rowNr, 1), span=(1, 1), flag=wx.ALL)
        self.rowNr += 1
        return check

    def AddCombo(self, label, options):
        combo = wx.ComboBox(self, -1, options[0], choices=options, style=wx.CB_DROPDOWN|wx.CB_READONLY)
        text = wx.StaticText(self, -1, label)
        self.GetSizer().Add(text, pos=(self.rowNr, 0), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.GetSizer().Add(combo, pos=(self.rowNr, 1), span=(1, 1), flag=wx.LEFT | wx.RIGHT)
        self.rowNr += 1
        return combo

    def AllowNext(self):
        return True

    def AllowBack(self):
        return True

    def StoreData(self):
        pass

class MachineSelectPage(InfoPage):
    def __init__(self, parent):
        super(MachineSelectPage, self).__init__(parent, _("Automatic Firmware Updater"))
        self.AddText(_("Check updates for which machine:\n"))

        BCN3DSigmaRadio = self.AddRadioButton("BCN3D Sigma")
        BCN3DSigmaRadio.Bind(wx.EVT_RADIOBUTTON, self.OnBCN3DSigmaSelect)
        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            BCN3DSigmaRadio.SetValue(True)
        BCN3DPlusRadio = self.AddRadioButton("BCN3D +")
        BCN3DPlusRadio.Bind(wx.EVT_RADIOBUTTON, self.OnBCN3DPlusSelect)
        if profile.getMachineSetting('machine_type') == 'BCN3DPlus':
            BCN3DPlusRadio.SetValue(True)
        BCN3DRRadio = self.AddRadioButton("BCN3D R")
        BCN3DRRadio.Bind(wx.EVT_RADIOBUTTON, self.OnBCN3DRSelect)
        if profile.getMachineSetting('machine_type') == 'BCN3DR':
            BCN3DRRadio.SetValue(True)




    def OnBCN3DSigmaSelect(self, e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdatesigma)

    def OnBCN3DPlusSelect(self, e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdateplus)

    def OnBCN3DRSelect(self, e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdater)

    def AllowBack(self):
        return False

class decideToUpdatePlus(InfoPage):
    def __init__(self, parent):
        super(decideToUpdatePlus, self).__init__(parent, _('Upgrade BCN3D Plus Firmware'))

        self.AddText(_('I am sorry, but Cura does not process firmware updates\n'
                       'for your machine.'))

class decideToUpdateR(InfoPage):
    def __init__(self, parent):
        super(decideToUpdateR, self).__init__(parent, _('Upgrade BCN3D R Firmware'))

        self.AddText(_('I am sorry, but Cura does not process firmware updates\n'
                       'for your machine.'))

class decideToUpdateSigma(InfoPage):
    def __init__(self, parent):
        super(decideToUpdateSigma, self).__init__(parent, _('Firmware Updater'))

        self._port = 'AUTO'
        self._baudrate = 250000

        if self._port == 'AUTO':
            print 'entramos en port auto despues de baudrate'
            programmer = stk500v2.Stk500v2()
            print 'antes',self._port
            if not programmer.isConnected():
                print 'not connected'
                for self._port in machineCom.serialList(False):
                    try:
                        print 'despues',self._port
                        programmer.connect(self._port)
                        print 'lo que devuelve', programmer.isConnected()
                        print self._baudrate
                        profile.putMachineSetting('serial_port_auto', self._port)
                        print 'hemos llegado despues del port'
                        print self._port
                        #wx.MessageBox('esto es lo que tenemoss',self._port)
                        programmer.close()
                        self._serial = serial.Serial(str(self._port), self._baudrate, timeout=1)
                        print self._serial
                        profile.putMachineSetting('self_serial', self._serial)
                        self._state = 'Online'
                        print 'bueno', self._state
                        break
                    except ispBase.IspError as (e):
                        self._state = 'Offline'
                        pass
                    programmer.close()
                if self._port not in machineCom.serialList(False):
                    self._state = 'Offline'
                    print 'malo',self._state


        if self._state == 'Offline':
            self.AddText(_('Please connect your printer to the computer.\n\n'
                           'In case you already had it connected and it was not detected,\n'
                           'please disconnect and connect again.\n\n'
                           'Once you have done this, you may press Connect && Upgrade to\n'
                           'continue with the process.\n\n'
                           '(Note: this may take a minute)\n'))
            connectButton = self.AddButton('Connect && Upgrade')
            connectButton.Bind(wx.EVT_BUTTON, self.OnWantToConnect)
            self.AddSeperator()
        if self._state == 'Online':
            self.AddText(_('We have detected a printer, please press Upgrade to continue\n'
                           'with the process.\n\n'
                           '(Note: this may take a minute)\n'))
            upgradeButton = self.AddButton('Upgrade')
            upgradeButton.Bind(wx.EVT_BUTTON, self.OnWantToUpgrade)
            self.AddSeperator()

    def OnWantToConnect(self,e):
        self._port = 'AUTO'
        self._baudrate = 250000

        if self._port == 'AUTO':
            print 'entramos en port auto despues de baudrate'
            programmer = stk500v2.Stk500v2()
            print 'antes', self._port
            if not programmer.isConnected():
                print 'not connected'
                for self._port in machineCom.serialList(False):
                    try:
                        print 'despues', self._port
                        programmer.connect(self._port)
                        print 'lo que devuelve', programmer.isConnected()
                        print self._baudrate
                        profile.putMachineSetting('serial_port_auto', self._port)
                        print 'hemos llegado despues del port'
                        print self._port
                        programmer.close()
                        self._serial = serial.Serial(str(self._port), self._baudrate, timeout=1)
                        print self._serial
                        profile.putMachineSetting('self_serial', self._serial)
                        self._state = 'Online'
                        print 'bueno', self._state
                        break
                    except ispBase.IspError as (e):
                        self._state = 'Offline'
                        pass
                    programmer.close()
                if self._port not in machineCom.serialList(False):
                    self._state = 'Offline'
                    print 'malo', self._state

        if self._state == 'Online':
            self._serial.close()
            self.readFirstLine()
            self.getFirmwareHardware()

    def OnWantToUpgrade(self,e):
        self._serial.close()
        self.readFirstLine()
        self.getFirmwareHardware()

    def readFirstLine(self):
            port = profile.getMachineSetting('serial_port_auto')
            ser = serial.Serial(
                port=str(port),
                baudrate=250000,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=2)

            print ser
            print("connected to: " + ser.portstr)

            ret = ''
            while ret == '':
                ret = ser.read(8)
                print 'devolvemos esto', ret


            self._version = ret

            print self._version

            ser.close()

    def getFirmwareHardware(self):
        ver = self._version

        if profile.getMachineSetting('machine_type') != 'BCN3DSigma' and profile.getMachineSetting(
                'machine_type') != 'BCN3DPlus' and profile.getMachineSetting('machine_type') != 'BCN3DR':
            wx.MessageBox(_("I am sorry, but Cura does not process firmware updates for your machine configuration."),
                          _("Firmware update"), wx.OK | wx.ICON_ERROR)
            return
        elif profile.getMachineSetting('machine_type') == 'BCN3DSigma' or profile.getMachineSetting(
                'machine_type') == 'BCN3DPlus' or profile.getMachineSetting('machine_type') == 'BCN3DR':
            myVersion = version.getLatestFHVersion(ver)


            if myVersion == None:
                return

            if version.downloadLatestFHVersion != None:
                org = os.getcwd()
                if sys.platform.startswith('win'):
                    self._dir = os.getcwd() + '\Compiled Firmware'
                    os.chdir(self._dir)
                elif sys.platform.startswith('darwin'):
                    self._dir = os.getcwd() + '/Compiled Firmware/'
                    os.chdir(self._dir)

                for filename in os.listdir(self._dir):
                    if filename.endswith(".hex"):
                        machineCom.InstallFirmware(self, filename)

                check = filter(lambda x: x.isdigit(), myVersion)
                print 'deberian ser solo digitos ', check
                goodOne = check[-3:]
                print 'good one ', goodOne


                for filename in os.listdir(org):
                    if filename.startswith("SD"):
                        print 'esto es el two ', filename
                        check2 = filter(lambda x: x.isdigit(), filename)
                        self._goodTwo = check2[-3:]
                        print 'esto es el two con solo numeros ', self._goodTwo

                if goodOne == self._goodTwo:
                    print 'hemos entrado porque tenemos que actualizar ficheros'
                    choice = wx.MessageBox(_("You need to update the files on your printers SD Card\n"
                                             "Press 'OK' to learn how to do it."), _("SD Files Updater"), wx.OK)
                    if choice == wx.OK:
                        os.chdir(org)
                        self.GetParent().FindWindowById(wx.ID_FORWARD).Enable()
                        self.GetParent().ShowPage(self.GetNext())

                elif goodOne != self._goodTwo:
                    print 'ya hemos acabado, no tenemos que actualizar nada para la SD'


                    wx.MessageBox(_("You are done!\n\nEnjoy the new version."), _("Firmware updater"), wx.OK | wx.ICON_INFORMATION)
                    #if thing == wx.OK:
                        #self.Bind(wx.wizard.EVT_WIZARD_FINISHED, thing)
                    #self.Destroy()
                    print 'done'


    def AllowBack(self):
        return True

    def AllowNext(self):
        return False

######## SD Wizard ###########
class disconnectPrinter(InfoPage):
    def __init__(self, parent):
        super(disconnectPrinter, self).__init__(parent, _('SD Update Wizard'))



        self.AddText(_('Please turn off your printer and disconnect the USB\n'
                       'cable from the computer.'))

    def AllowNext(self):
        return True

class undoCover(InfoPage):
    def __init__(self, parent):
        super(undoCover, self).__init__(parent, _('SD Update Wizard'))

        self.AddText(_('First of all undo the screw holding the LCD Cover.'))

        self.firstBit = wx.Bitmap(resources.getPathForImage('cover1.png'))
        self.AddBitmap(self.firstBit)

    def AllowNext(self):
        return True

class removeSDCard(InfoPage):
    def __init__(self, parent):
        super(removeSDCard, self).__init__(parent, _('SD Update Wizard'))

        self.AddText(_('Now take out the micro SD card. You just need to\n'
                       'push it in and the SD card will come off. Be careful\n'
                       'not to lose the SD card inside the printer.'))

        self.secondBit = wx.Bitmap(resources.getPathForImage('cover2.png'))
        self.AddBitmap(self.secondBit)


    def AllowNext(self):
        return True

class addNewFiles(InfoPage):
    def __init__(self, parent):
        super(addNewFiles, self).__init__(parent, _('SD Update Wizard'))

        self.AddText(_('Connect the SD card to your computer and substitute\n'
                       'the old files for the new ones. We recommned that you\n'
                       'delete all of the old files and copy the new ones.\n\n'
                       'Press on the button below to find the new SD files\n'
                       'you need.\n'))

        fileButton = self.AddButton('SD Files')
        fileButton.Bind(wx.EVT_BUTTON, self.onGetFiles)


    def onGetFiles(self,e):
        os.startfile(os.getcwd())
        self.GetParent().FindWindowById(wx.ID_FORWARD).Enable()
        self.GetParent().ShowPage(self.GetNext())

    def AllowNext(self):
        return True

class youAreDone(InfoPage):
    def __init__(self, parent):
        super(youAreDone, self).__init__(parent, _('SD Update Wizard'))

        self.AddText(_('You are done!\n\n'
                       'Make sure you insert the SD card back in the LCD\n'
                       'display and close the LCD Cover.\n\n'
                       'Enjoy the new version!\n'))

    def AllowNext(self):
        return True

#Where you edit the pages and how they work
class ConfigFirmware(wx.wizard.Wizard):
    def __init__(self):
        super(ConfigFirmware, self).__init__(None, -1, _("Machine Firmware Updater"))

        self.Bind(wx.wizard.EVT_WIZARD_FINISHED, self.OnCancel)
        self.Bind(wx.wizard.EVT_WIZARD_PAGE_CHANGED, self.OnPageChanged)
        self.Bind(wx.wizard.EVT_WIZARD_PAGE_CHANGING, self.OnPageChanging)
        self.Bind(wx.wizard.EVT_WIZARD_FINISHED, self.OnFinish)


        self.machineSelectPage = MachineSelectPage(self)
        self.decidetoupdatesigma = decideToUpdateSigma(self)
        self.decidetoupdateplus = decideToUpdatePlus(self)
        self.decidetoupdater = decideToUpdateR(self)
        self.disconnectprinter = disconnectPrinter(self)
        self.undocover = undoCover(self)
        self.removesdcard = removeSDCard(self)
        self.addnewfiles = addNewFiles(self)
        self.youaredone = youAreDone(self)

        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            wx.wizard.WizardPageSimple.Chain(self.machineSelectPage, self.decidetoupdatesigma)
            wx.wizard.WizardPageSimple.Chain(self.decidetoupdatesigma, self.disconnectprinter)
            wx.wizard.WizardPageSimple.Chain(self.disconnectprinter, self.undocover)
            wx.wizard.WizardPageSimple.Chain(self.undocover, self.removesdcard)
            wx.wizard.WizardPageSimple.Chain(self.removesdcard, self.addnewfiles)
            wx.wizard.WizardPageSimple.Chain(self.addnewfiles, self.youaredone)

        self.FitToPage(self.machineSelectPage)
        self.GetPageAreaSizer().Add(self.machineSelectPage)

        self.RunWizard(self.machineSelectPage)
        self.Destroy()

    def OnPageChanging(self, e):
        e.GetPage().StoreData()

    def OnPageChanged(self, e):
        if e.GetPage().AllowNext():
            self.FindWindowById(wx.ID_FORWARD).Enable()
        else:
            self.FindWindowById(wx.ID_FORWARD).Disable()
        if e.GetPage().AllowBack():
            self.FindWindowById(wx.ID_BACKWARD).Enable()
        else:
            self.FindWindowById(wx.ID_BACKWARD).Disable()

    def OnCancel(self, e):
        self.Destroy()

    def OnFinish(self, e):
        self.Destroy()


