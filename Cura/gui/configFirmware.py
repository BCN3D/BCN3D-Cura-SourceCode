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
from Cura.util import machineFirmCom
from Cura.util import profile
from Cura.util import resources
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
        self.AddText(_("Check updates for which machine:"))

        BCN3DSigmaRadio = self.AddRadioButton("BCN3D " + u"\u03A3", style=wx.RB_GROUP)
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

    def OnBCN3DSigmaSelect(self,e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdatesigma)

    def OnBCN3DPlusSelect(self,e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdateplus)

    def OnBCN3DRSelect(self,e):
        wx.wizard.WizardPageSimple.Chain(self, self.GetParent().decidetoupdater)

    def AllowBack(self):
        return False

class decideToUpdateSigma(InfoPage):
    def __init__(self, parent):
        super(decideToUpdateSigma, self).__init__(parent, _('Upgrade BCN3D ' + u"\u03A3" + ' Firmware'))
        self.AddText(_('Are you sure you want to upgrade your firmware to the \nnewest available version?'))
        self.AddSeperator()
        upgradeButton = self.AddButton('Upgrade Firmware')
        upgradeButton.Bind(wx.EVT_BUTTON, self.OnFirstConnect)

    def AllowNext(self):
        return False

    def AllowBack(self):
        return True

    def OnFirstConnect(self, e):
        self.GetParent().FindWindowById(wx.ID_FORWARD).Enable()
        self.GetParent().ShowPage(self.GetNext())

class FirstConnectPrinterSigma(InfoPage):
    def __init__(self, parent):
        super(FirstConnectPrinterSigma,self).__init__(parent, _("Printer connection"))
        self.AddText(_('Please connect your printer to the computer. \nOnce you see "Connected" you may proceed to the next step.'))
        self.checkBitmap = wx.Bitmap(resources.getPathForImage('checkmark.png'))
        self.crossBitmap = wx.Bitmap(resources.getPathForImage('cross.png'))
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))

        connectPritner = self.AddButton(_("Connect printer"))
        connectPritner.Bind(wx.EVT_BUTTON, self.OnCheckClick)
        connectPritner.Enable(True)
        self.AddSeperator()
        self.commState = self.AddCheckmark(_("Communication:"), self.unknownBitmap)
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))
        self.infoBox = self.AddInfoBox()
        self.machineState = self.AddText("")
        self.errorLogButton = self.AddButton(_("Show error log"))
        self.errorLogButton.Show(False)
        self.comm = None
        self.Bind(wx.EVT_BUTTON, self.OnErrorLog, self.errorLogButton)
        self.AddSeperator()
        self.AddText(_('Press on the following button to know your current \nfirmware version and check whether there are new releases. \nThis might take a few seconds.'))
        getFirstLine = self.AddButton(_("Get firmware version"))
        getFirstLine.Bind(wx.EVT_BUTTON, self.OnGetFirstLine)
        self.AddSeperator()
        self.AddText(_('Sometimes when releasing new firmware updates, it is \nnecessary to update the files of the LCD Display in order \nto get new functionalities and menus.'))
        openSDFiles = self.AddButton(_("Open SD Files"))
        openSDFiles.Bind(wx.EVT_BUTTON, self.OnOpenSDFiles)
        howToOpen = self.AddButton(_("How to Update SD Files"))
        howToOpen.Bind(wx.EVT_BUTTON, self.OnHowToOpen)
        self.AddSeperator()



    def __del__(self):
        if self.comm is not None:
            self.comm.close()

    def AllowNext(self):
        return False

    def OnCheckClick(self, e=None):
        self.errorLogButton.Show(False)
        if self.comm is not None:
            self.comm.close()
            del self.comm
            self.comm = None
            wx.CallAfter(self.OnCheckClick)
            return
        self.infoBox.SetBusy(_("Connecting to machine."))
        self.commState.SetBitmap(self.unknownBitmap)
        self.comm = machineCom.MachineCom(callbackObject=self)
        self.checkupState = 0

    def OnErrorLog(self, e):
        printWindow.LogWindow('\n'.join(self.comm.getLog()))

    def mcLog(self, message):
        pass

    def mcStateChange(self, state):
        if self.comm is None:
            return
        if self.comm.isOperational():
            wx.CallAfter(self.commState.SetBitmap, self.checkBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("%s") % (self.comm.getStateString()))
            wx.CallAfter(self.infoBox.SetReadyIndicator)
        elif self.comm.isError():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.infoBox.SetError, _("Failed to establish connection with the printer."), 'https://github.com/BCN3D/BCN3D-Cura-Windows/issues')
            wx.CallAfter(self.machineState.SetLabel, '%s' % (self.comm.getErrorString()))
            wx.CallAfter(self.errorLogButton.Show, True)
            wx.CallAfter(self.Layout)
        elif self.comm.isClosed():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("Failed to establish connection with the printer."))
            wx.CallAfter(self.infoBox.SetErrorIndicator)
        else:
            wx.CallAfter(self.machineState.SetLabel, _("Communication State: %s") % (self.comm.getStateString()))

    def mcMessage(self, message):
        if self.checkupState >= 3 and self.checkupState < 10 and ('_min' in message or '_max' in message):
            for data in message.split(' '):
                if ':' in data:
                    tag, value = data.split(':', 1)
                    if tag == 'x_min':
                        self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'x_max':
                        self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_min':
                        self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_max':
                        self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_min':
                        self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_max':
                        self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if ':' in message:
                tag, value = map(str.strip, message.split(':', 1))
                if tag == 'x_min':
                    self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'x_max':
                    self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_min':
                    self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_max':
                    self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_min':
                    self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_max':
                    self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if 'z_max' in message:
                self.comm.sendCommand('M119')

            if self.checkupState == 3:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 5
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
                    else:
                        self.checkupState = 4
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the right X endstop."))
            elif self.checkupState == 4:
                if not self.xMinStop and self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 5
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
            elif self.checkupState == 5:
                if self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 6
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the front Y endstop."))
            elif self.checkupState == 6:
                if not self.xMinStop and not self.xMaxStop and self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 8
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
                    else:
                        self.checkupState = 7
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the back Y endstop."))
            elif self.checkupState == 7:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 8
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
            elif self.checkupState == 8:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 10
                        self.comm.close()
                        wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                        wx.CallAfter(self.infoBox.SetReadyIndicator)
                    else:
                        self.checkupState = 9
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the bottom Z endstop."))
            elif self.checkupState == 9:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and self.zMaxStop:
                    self.checkupState = 10
                    self.comm.close()
                    wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                    wx.CallAfter(self.infoBox.SetReadyIndicator)

    def mcProgress(self, lineNr):
        pass

    def mcZChange(self, newZ):
        pass

    def OnGetFirstLine(self, e = None):
        if self.comm.isOperational():
            self.comm.readFirstLine()
            self.comm.getFirmwareHardware()

    def OnOpenSDFiles(self, e):
        home = os.path.expanduser('~')
        os.startfile(home + '\Documents\BCN3DSigma')

    def OnHowToOpen(self, e):
        webbrowser.open('https://github.com/BCN3D/BCN3D-Cura-Windows/wiki/Updating-the-SD-Files-from-the-LCD-Display')


#### Updater for BCN3D Plus #####
class decideToUpdatePlus(InfoPage):
    def __init__(self, parent):
        super(decideToUpdatePlus, self).__init__(parent, _('Upgrade BCN3D + Firmware'))
        self.AddText(_('Are you sure you want to upgrade your firmware to the \nnewest available version?'))
        self.AddSeperator()
        upgradeButton = self.AddButton('Upgrade Firmware')
        upgradeButton.Bind(wx.EVT_BUTTON, self.OnFirstConnect)

    def AllowNext(self):
        return False

    def AllowBack(self):
        return True

    def OnFirstConnect(self, e):
        self.GetParent().FindWindowById(wx.ID_FORWARD).Enable()
        self.GetParent().ShowPage(self.GetNext())

class FirstConnectPrinterPlus(InfoPage):
    def __init__(self, parent):
        super(FirstConnectPrinterPlus,self).__init__(parent, _("Printer connection"))
        self.AddText(_('Please connect your printer to the computer. \nOnce you see "Connected" you may proceed to the next step.'))
        self.checkBitmap = wx.Bitmap(resources.getPathForImage('checkmark.png'))
        self.crossBitmap = wx.Bitmap(resources.getPathForImage('cross.png'))
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))

        connectPritner = self.AddButton(_("Connect printer"))
        connectPritner.Bind(wx.EVT_BUTTON, self.OnCheckClick)
        connectPritner.Enable(True)
        self.AddSeperator()
        self.commState = self.AddCheckmark(_("Communication:"), self.unknownBitmap)
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))
        self.infoBox = self.AddInfoBox()
        self.machineState = self.AddText("")
        self.errorLogButton = self.AddButton(_("Show error log"))
        self.errorLogButton.Show(False)
        self.comm = None
        self.Bind(wx.EVT_BUTTON, self.OnErrorLog, self.errorLogButton)
        self.AddSeperator()
        self.AddText(_('Press on the following button to know your current \nfirmware version and check whether there are new releases. \nThis might take a few seconds.'))
        getFirstLine = self.AddButton(_("Get firmware version"))
        getFirstLine.Bind(wx.EVT_BUTTON, self.OnGetFirstLine)
        self.AddSeperator()


    def __del__(self):
        if self.comm is not None:
            self.comm.close()

    def AllowNext(self):
        return True


    def OnCheckClick(self, e=None):
        self.errorLogButton.Show(False)
        if self.comm is not None:
            self.comm.close()
            del self.comm
            self.comm = None
            wx.CallAfter(self.OnCheckClick)
            return
        self.infoBox.SetBusy(_("Connecting to machine."))
        self.commState.SetBitmap(self.unknownBitmap)
        self.comm = machineCom.MachineCom(callbackObject=self)
        self.checkupState = 0

    def OnErrorLog(self, e):
        printWindow.LogWindow('\n'.join(self.comm.getLog()))

    def mcLog(self, message):
        pass

    def mcStateChange(self, state):
        if self.comm is None:
            return
        if self.comm.isOperational():
            wx.CallAfter(self.commState.SetBitmap, self.checkBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("%s") % (self.comm.getStateString()))
            wx.CallAfter(self.infoBox.SetReadyIndicator)
        elif self.comm.isError():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.infoBox.SetError, _("Failed to establish connection with the printer."), 'http://wiki.ultimaker.com/Cura:_Connection_problems')
            wx.CallAfter(self.machineState.SetLabel, '%s' % (self.comm.getErrorString()))
            wx.CallAfter(self.errorLogButton.Show, True)
            wx.CallAfter(self.Layout)
        elif self.comm.isClosed():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("Failed to establish connection with the printer."))
            wx.CallAfter(self.infoBox.SetErrorIndicator)
        else:
            wx.CallAfter(self.machineState.SetLabel, _("Communication State: %s") % (self.comm.getStateString()))

    def mcMessage(self, message):
        if self.checkupState >= 3 and self.checkupState < 10 and ('_min' in message or '_max' in message):
            for data in message.split(' '):
                if ':' in data:
                    tag, value = data.split(':', 1)
                    if tag == 'x_min':
                        self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'x_max':
                        self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_min':
                        self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_max':
                        self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_min':
                        self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_max':
                        self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if ':' in message:
                tag, value = map(str.strip, message.split(':', 1))
                if tag == 'x_min':
                    self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'x_max':
                    self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_min':
                    self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_max':
                    self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_min':
                    self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_max':
                    self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if 'z_max' in message:
                self.comm.sendCommand('M119')

            if self.checkupState == 3:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 5
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
                    else:
                        self.checkupState = 4
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the right X endstop."))
            elif self.checkupState == 4:
                if not self.xMinStop and self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 5
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
            elif self.checkupState == 5:
                if self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 6
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the front Y endstop."))
            elif self.checkupState == 6:
                if not self.xMinStop and not self.xMaxStop and self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 8
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
                    else:
                        self.checkupState = 7
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the back Y endstop."))
            elif self.checkupState == 7:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 8
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
            elif self.checkupState == 8:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 10
                        self.comm.close()
                        wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                        wx.CallAfter(self.infoBox.SetReadyIndicator)
                    else:
                        self.checkupState = 9
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the bottom Z endstop."))
            elif self.checkupState == 9:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and self.zMaxStop:
                    self.checkupState = 10
                    self.comm.close()
                    wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                    wx.CallAfter(self.infoBox.SetReadyIndicator)

    def mcProgress(self, lineNr):
        pass

    def mcZChange(self, newZ):
        pass

    def OnGetFirstLine(self, e = None):
        if self.comm.isOperational():
            self.comm.readFirstLine()
            self.comm.getFirmwareHardware()


##### Updater for BCN3D R ######
class decideToUpdateR(InfoPage):
    def __init__(self, parent):
        super(decideToUpdateR, self).__init__(parent, _('Upgrade BCN3D R Firmware'))
        self.AddText(_('Are you sure you want to upgrade your firmware to the \nnewest available version?'))
        self.AddSeperator()
        upgradeButton = self.AddButton('Upgrade Firmware')
        upgradeButton.Bind(wx.EVT_BUTTON, self.OnFirstConnect)

    def AllowNext(self):
        return False

    def AllowBack(self):
        return True

    def OnFirstConnect(self, e):
        self.GetParent().FindWindowById(wx.ID_FORWARD).Enable()
        self.GetParent().ShowPage(self.GetNext())

class FirstConnectPrinterR(InfoPage):
    def __init__(self, parent):
        super(FirstConnectPrinterR,self).__init__(parent, _("Printer connection"))
        self.AddText(_('Please connect your printer to the computer. \nOnce you see "Connected" you may proceed to the next step.'))
        self.checkBitmap = wx.Bitmap(resources.getPathForImage('checkmark.png'))
        self.crossBitmap = wx.Bitmap(resources.getPathForImage('cross.png'))
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))

        connectPritner = self.AddButton(_("Connect printer"))
        connectPritner.Bind(wx.EVT_BUTTON, self.OnCheckClick)
        connectPritner.Enable(True)
        self.AddSeperator()
        self.commState = self.AddCheckmark(_("Communication:"), self.unknownBitmap)
        self.unknownBitmap = wx.Bitmap(resources.getPathForImage('question.png'))
        self.infoBox = self.AddInfoBox()
        self.machineState = self.AddText("")
        self.errorLogButton = self.AddButton(_("Show error log"))
        self.errorLogButton.Show(False)
        self.comm = None
        self.Bind(wx.EVT_BUTTON, self.OnErrorLog, self.errorLogButton)
        self.AddSeperator()
        self.AddText(_('Press on the following button to know your current \nfirmware version and check whether there are new releases. \nThis might take a few seconds.'))
        getFirstLine = self.AddButton(_("Get firmware version"))
        getFirstLine.Bind(wx.EVT_BUTTON, self.OnGetFirstLine)
        self.AddSeperator()


    def __del__(self):
        if self.comm is not None:
            self.comm.close()

    def AllowNext(self):
        return True

    def OnCheckClick(self, e=None):
        self.errorLogButton.Show(False)
        if self.comm is not None:
            self.comm.close()
            del self.comm
            self.comm = None
            wx.CallAfter(self.OnCheckClick)
            return
        self.infoBox.SetBusy(_("Connecting to machine."))
        self.commState.SetBitmap(self.unknownBitmap)
        self.comm = machineCom.MachineCom(callbackObject=self)
        self.checkupState = 0

    def OnErrorLog(self, e):
        printWindow.LogWindow('\n'.join(self.comm.getLog()))

    def mcLog(self, message):
        pass

    def mcStateChange(self, state):
        if self.comm is None:
            return
        if self.comm.isOperational():
            wx.CallAfter(self.commState.SetBitmap, self.checkBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("%s") % (self.comm.getStateString()))
            wx.CallAfter(self.infoBox.SetReadyIndicator)
        elif self.comm.isError():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.infoBox.SetError, _("Failed to establish connection with the printer."), 'http://wiki.ultimaker.com/Cura:_Connection_problems')
            wx.CallAfter(self.machineState.SetLabel, '%s' % (self.comm.getErrorString()))
            wx.CallAfter(self.errorLogButton.Show, True)
            wx.CallAfter(self.Layout)
        elif self.comm.isClosed():
            wx.CallAfter(self.commState.SetBitmap, self.crossBitmap)
            wx.CallAfter(self.machineState.SetLabel, _("Failed to establish connection with the printer."))
            wx.CallAfter(self.infoBox.SetErrorIndicator)
        else:
            wx.CallAfter(self.machineState.SetLabel, _("Communication State: %s") % (self.comm.getStateString()))

    def mcMessage(self, message):
        if self.checkupState >= 3 and self.checkupState < 10 and ('_min' in message or '_max' in message):
            for data in message.split(' '):
                if ':' in data:
                    tag, value = data.split(':', 1)
                    if tag == 'x_min':
                        self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'x_max':
                        self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_min':
                        self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'y_max':
                        self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_min':
                        self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                    if tag == 'z_max':
                        self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if ':' in message:
                tag, value = map(str.strip, message.split(':', 1))
                if tag == 'x_min':
                    self.xMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'x_max':
                    self.xMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_min':
                    self.yMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'y_max':
                    self.yMaxStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_min':
                    self.zMinStop = (value == 'H' or value == 'TRIGGERED')
                if tag == 'z_max':
                    self.zMaxStop = (value == 'H' or value == 'TRIGGERED')
            if 'z_max' in message:
                self.comm.sendCommand('M119')

            if self.checkupState == 3:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 5
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
                    else:
                        self.checkupState = 4
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the right X endstop."))
            elif self.checkupState == 4:
                if not self.xMinStop and self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 5
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the left X endstop."))
            elif self.checkupState == 5:
                if self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 6
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the front Y endstop."))
            elif self.checkupState == 6:
                if not self.xMinStop and not self.xMaxStop and self.yMinStop and not self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 8
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
                    else:
                        self.checkupState = 7
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the back Y endstop."))
            elif self.checkupState == 7:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and self.yMaxStop and not self.zMinStop and not self.zMaxStop:
                    self.checkupState = 8
                    wx.CallAfter(self.infoBox.SetAttention, _("Please press the top Z endstop."))
            elif self.checkupState == 8:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and self.zMinStop and not self.zMaxStop:
                    if profile.getMachineSetting('machine_type') == 'ultimaker_plus':
                        self.checkupState = 10
                        self.comm.close()
                        wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                        wx.CallAfter(self.infoBox.SetReadyIndicator)
                    else:
                        self.checkupState = 9
                        wx.CallAfter(self.infoBox.SetAttention, _("Please press the bottom Z endstop."))
            elif self.checkupState == 9:
                if not self.xMinStop and not self.xMaxStop and not self.yMinStop and not self.yMaxStop and not self.zMinStop and self.zMaxStop:
                    self.checkupState = 10
                    self.comm.close()
                    wx.CallAfter(self.infoBox.SetInfo, _("Checkup finished"))
                    wx.CallAfter(self.infoBox.SetReadyIndicator)

    def mcProgress(self, lineNr):
        pass

    def mcZChange(self, newZ):
        pass

    def OnGetFirstLine(self, e = None):
        if self.comm.isOperational():
            self.comm.readFirstLine()
            self.comm.getFirmwareHardware()



#Where you edit the pages and how they work
class ConfigFirmware(wx.wizard.Wizard):
    def __init__(self, addNew = False):
        super(ConfigFirmware, self).__init__(None, -1, _("Machine Firmware Updater"))

        self._old_machine_index = int(profile.getPreferenceFloat('active_machine'))
        if addNew:
            profile.setActiveMachine(profile.getMachineCount())

        self.Bind(wx.wizard.EVT_WIZARD_CANCEL, self.OnCancel)
        self.Bind(wx.wizard.EVT_WIZARD_PAGE_CHANGED, self.OnPageChanged)
        self.Bind(wx.wizard.EVT_WIZARD_PAGE_CHANGING, self.OnPageChanging)
        self.Bind(wx.wizard.EVT_WIZARD_FINISHED, self.OnFinish)


        self.machineSelectPage = MachineSelectPage(self)
        self.decidetoupdatesigma = decideToUpdateSigma(self)
        self.firstconnectprintersigma = FirstConnectPrinterSigma(self)
        self.decidetoupdateplus = decideToUpdatePlus(self)
        self.firstconnectprinterplus = FirstConnectPrinterPlus(self)
        self.decidetoupdater = decideToUpdateR(self)
        self.firstconnectprinterr = FirstConnectPrinterR(self)


        if profile.getMachineSetting('machine_type') == 'BCN3DSigma':
            wx.wizard.WizardPageSimple.Chain(self.machineSelectPage, self.decidetoupdatesigma)
            wx.wizard.WizardPageSimple.Chain(self.decidetoupdatesigma, self.firstconnectprintersigma)
        if profile.getMachineSetting('machine_type') == 'BCN3DPlus':
            wx.wizard.WizardPageSimple.Chain(self.machineSelectPage, self.decidetoupdateplus)
            wx.wizard.WizardPageSimple.Chain(self.decidetoupdateplus, self.firstconnectprinterplus)
        if profile.getMachineSetting('machine_type') == 'BCN3DR':
            wx.wizard.WizardPageSimple.Chain(self.machineSelectPage, self.decidetoupdater)
            wx.wizard.WizardPageSimple.Chain(self.decidetoupdater, self.firstconnectprinterr)


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

    def OnCancel():
        wizard.Destroy()
    
    def OnFinish():
        wizard.Destroy()






