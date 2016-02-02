__copyright__ = "Copyright (C) 2013 David Braam - Released under terms of the AGPLv3 License"

import wx
from Cura.gui import firmwareInstall
from Cura.util import version
from Cura.util import profile

class newVersionDialog(wx.Dialog):
	def __init__(self):
		super(newVersionDialog, self).__init__(None, title="Welcome to the new version!")

		wx.EVT_CLOSE(self, self.OnClose)

		p = wx.Panel(self)
		self.panel = p
		s = wx.BoxSizer()
		self.SetSizer(s)
		s.Add(p, flag=wx.ALL, border=15)
		s = wx.BoxSizer(wx.VERTICAL)
		p.SetSizer(s)

		title = wx.StaticText(p, -1, 'Cura-BCN3D ' + version.getVersion())
		title.SetFont(wx.Font(18, wx.SWISS, wx.NORMAL, wx.BOLD))
		s.Add(title, flag=wx.ALIGN_CENTRE|wx.EXPAND|wx.BOTTOM, border=5)
		s.Add(wx.StaticText(p, -1, 'Welcome to the new version of Cura.'))
		s.Add(wx.StaticText(p, -1, '(This dialog is only shown once)'))
		s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
		s.Add(wx.StaticText(p, -1, 'New in this version:'))
		s.Add(wx.StaticText(p, -1, '* Added settings for BCN3D Technologies printers'))
		s.Add(wx.StaticText(p, -1, '* Changed some parts of the interface to give a better user experience'))
		s.Add(wx.StaticText(p, -1, '* BCN3D Sigma is automatically set to double extrusion'))

		self.hasBCN3DSigma = None
		self.hasBCN3DPlus = None
		self.hasBCN3DR = None
		self.hasUltimaker = None
		self.hasUltimaker2 = None

		for n in xrange(0, profile.getMachineCount()):
			if profile.getMachineSetting('machine_type', n) == 'BCN3DSigma':
				self.hasBCN3DSigma = n
			if profile.getMachineSetting('machine_type', n) == 'BCN3DPlus':
				self.hasBCN3DPlus = n
			if profile.getMachineSetting('machine_type', n) == 'BCN3DR':
				self.hasBCN3DR = n
			if profile.getMachineSetting('machine_type', n) == 'ultimaker':
				self.hasUltimaker = n
			if profile.getMachineSetting('machine_type', n) == 'ultimaker2':
				self.hasUltimaker2 = n
		if self.hasBCN3DSigma is not None and False:
			s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
			s.Add(wx.StaticText(p, -1, 'New firmware for your BCN3D Sigma:'))
			s.Add(wx.StaticText(p, -1, '* .'))
			button = wx.Button(p, -1, 'Install now')
			self.Bind(wx.EVT_BUTTON, self.OnBCN3DSigmaFirmware, button)
			s.Add(button, flag=wx.TOP, border=5)
		if self.hasBCN3DPlus is not None and False:
			s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
			s.Add(wx.StaticText(p, -1, 'New firmware for your BCN3D Plus:'))
			s.Add(wx.StaticText(p, -1, '* .'))
			button = wx.Button(p, -1, 'Install now')
			self.Bind(wx.EVT_BUTTON, self.OnBCN3DPlusFirmware, button)
			s.Add(button, flag=wx.TOP, border=5)
		if self.hasBCN3DR is not None and False:
			s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
			s.Add(wx.StaticText(p, -1, 'New firmware for your BCN3D R:'))
			s.Add(wx.StaticText(p, -1, '* .'))
			button = wx.Button(p, -1, 'Install now')
			self.Bind(wx.EVT_BUTTON, self.OnBCN3DRFirmware, button)
			s.Add(button, flag=wx.TOP, border=5)
		if self.hasUltimaker is not None and False:
			s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
			s.Add(wx.StaticText(p, -1, 'New firmware for your Ultimaker Original:'))
			s.Add(wx.StaticText(p, -1, '* .'))
			button = wx.Button(p, -1, 'Install now')
			self.Bind(wx.EVT_BUTTON, self.OnUltimakerFirmware, button)
			s.Add(button, flag=wx.TOP, border=5)
		if self.hasUltimaker2 is not None and False:
			s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
			s.Add(wx.StaticText(p, -1, 'New firmware for your Ultimaker2: '))
			s.Add(wx.StaticText(p, -1, '* .'))
			button = wx.Button(p, -1, 'Install now')
			self.Bind(wx.EVT_BUTTON, self.OnUltimaker2Firmware, button)
			s.Add(button, flag=wx.TOP, border=5)


		s.Add(wx.StaticLine(p), flag=wx.EXPAND|wx.TOP|wx.BOTTOM, border=10)
		button = wx.Button(p, -1, 'Ok')
		self.Bind(wx.EVT_BUTTON, self.OnOk, button)
		s.Add(button, flag=wx.TOP|wx.ALIGN_RIGHT, border=5)

		self.Fit()
		self.Centre()

	def OnBCN3DSigmaFirmware(self, e):
		firmwareInstall.InstallFirmware(machineIndex=self.hasBCN3DSigma)

	def OnBCN3DPlusFirmware(self, e):
		firmwareInstall.InstallFirmware(machineIndex=self.hasBCN3DPlus)

	def OnBCN3DRFirmware(self, e):
		firmwareInstall.InstallFirmware(machineIndex=self.hasBCN3DR)

	def OnUltimakerFirmware(self, e):
		firmwareInstall.InstallFirmware(machineIndex=self.hasUltimaker)

	def OnUltimaker2Firmware(self, e):
		firmwareInstall.InstallFirmware(machineIndex=self.hasUltimaker2)

	def OnOk(self, e):
		self.Close()

	def OnClose(self, e):
		self.Destroy()
