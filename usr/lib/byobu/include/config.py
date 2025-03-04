#!/usr/bin/env python3
#
#    config.py
#    Copyright (C) 2008 Canonical Ltd.
#    Copyright (C) 2008-2014 Dustin Kirkland <kirkland@byobu.org>

#
#    Authors: Nick Barcet <nick.barcet@ubuntu.com>
#             Dustin Kirkland <kirkland@byobu.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

# If you change any strings, please generate localization information with:
#       ./debian/rules get-po

from __future__ import print_function
import sys
import os
import os.path
import time
import string
import subprocess
import gettext
import glob


def error(msg):
	print("ERROR: %s" % msg)
	sys.exit(1)


try:
	import snack
	from snack import *
except Exception:
	error("Could not import the python snack module")


PKG = "byobu"
HOME = os.getenv("HOME")
USER = os.getenv("USER")
BYOBU_CONFIG_DIR = os.getenv("BYOBU_CONFIG_DIR", HOME + "/.byobu")
BYOBU_RUN_DIR = os.getenv("BYOBU_RUN_DIR", HOME + "/.cache/byobu")
BYOBU_PREFIX = os.getenv("BYOBU_PREFIX", "@prefix@")
SHARE = BYOBU_PREFIX + '/share/' + PKG
DOC = BYOBU_PREFIX + '/share/doc/' + PKG
if not os.path.exists(SHARE):
	SHARE = BYOBU_CONFIG_DIR + "/" + SHARE
if not os.path.exists(DOC):
	DOC = BYOBU_PREFIX + '/share/doc/packages/' + PKG
if not os.path.exists(DOC):
	DOC = BYOBU_CONFIG_DIR + "/" + DOC
DEF_ESC = "A"
RELOAD = "If you are using the default set of keybindings, press\n<F5> or <ctrl-a-R> to activate these changes.\n\nOtherwise, exit this session and start a new one."
RELOAD_FLAG = "%s/reload-required" % (BYOBU_RUN_DIR)
ESC = ''
snack.hotkeys[ESC] = ord(ESC)
snack.hotkeys[ord(ESC)] = ESC
gettext.bindtextdomain(PKG, SHARE + '/po')
gettext.textdomain(PKG)
_ = gettext.gettext


def ioctl_GWINSZ(fd):
	# Discover terminal width
	try:
		import fcntl
		import termios
		import struct
		import os
		cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
	except Exception:
		return None
	return cr


def reload_required():
	try:
		if not os.path.exists(BYOBU_CONFIG_DIR):
			# 493 (decimal) is 0755 (octal)
			# Use decimal for portability across all python versions
			os.makedirs(BYOBU_CONFIG_DIR, 493)
		f = open(RELOAD_FLAG, 'w')
		f.close()
	except Exception:
		True


def terminal_size():
	# decide on some terminal size
	cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
	# try open fds
	if not cr:
		# ...then ctty
		try:
			fd = os.open(os.ctermid(), os.O_RDONLY)
			cr = ioctl_GWINSZ(fd)
			os.close(fd)
		except Exception:
			pass
	if not cr:
		# env vars or finally defaults
		try:
			cr = (env['LINES'], env['COLUMNS'])
		except Exception:
			cr = (25, 80)
	# reverse rows, cols
	return int(cr[1] - 5), int(cr[0] - 5)


def menu(snackScreen, size, isInstalled):
	if isInstalled:
		installtext = _("Byobu currently launches at login (toggle off)")
	else:
		installtext = _("Byobu currently does not launch at login (toggle on)")
	li = Listbox(height=6, width=60, returnExit=1)
	li.append(_("Help -- Quick Start Guide"), 1)
	li.append(_("Toggle status notifications"), 2)
	li.append(_("Change escape sequence"), 3)
	li.append(installtext, 4)
	bb = ButtonBar(snackScreen, (("Exit", "exit", ESC),), compact=1)
	g = GridForm(snackScreen, _(" Byobu Configuration Menu"), 1, 2)
	g.add(li, 0, 0, padding=(4, 2, 4, 2))
	g.add(bb, 0, 1, padding=(1, 1, 0, 0))
	if bb.buttonPressed(g.runOnce()) == "exit":
		return 0
	else:
		return li.current()


def messagebox(snackScreen, width, height, title, text, scroll=0, buttons=((_("Okay"), "okay"), (_("Cancel"), "cancel", ESC))):
	t = Textbox(width, height, text, scroll=scroll)
	bb = ButtonBar(snackScreen, buttons, compact=1)
	g = GridForm(snackScreen, title, 1, 2)
	g.add(t, 0, 0, padding=(0, 0, 0, 0))
	g.add(bb, 0, 1, padding=(1, 1, 0, 0))
	return bb.buttonPressed(g.runOnce())


def help(snackScreen, size):
	f = open(DOC + '/help.tmux.txt')
	text = f.read()
	f.close()
	text = text.replace("<esckey>", getesckey(), 1)
	t = Textbox(67, 16, text, scroll=1, wrap=1)
	bb = ButtonBar(snackScreen, ((_("Menu"), "menu", ESC),), compact=1)
	g = GridForm(snackScreen, _("Byobu Help"), 2, 4)
	g.add(t, 1, 0)
	g.add(bb, 1, 1, padding=(1, 1, 0, 0))
	button = bb.buttonPressed(g.runOnce())
	return 100


def readstatus():
	status = {}
	glo = {}
	loc = {}
	for f in [SHARE + '/status/status', BYOBU_CONFIG_DIR + '/status']:
		if os.path.exists(f):
			try:
				exec(open(f).read(), glo, loc)
			except Exception:
				error("Invalid configuration [%s]" % f)
			items = "%s %s" % (loc["tmux_left"], loc["tmux_right"])
			for i in items.split():
				if i.startswith("#"):
					i = i.replace("#", "")
					status[i] = "0"
				else:
					status[i] = "1"
	li = []
	keys = list(status.keys())
	for i in sorted(keys):
		window = [int(status[i]), i]
		li.append(window)
	return li


def genstatusstring(s, status):
	new = ""
	glo = {}
	loc = {}
	exec(open(SHARE + '/status/status').read(), glo, loc)
	for i in loc[s].split():
		if i.startswith("#"):
			i = i.replace("#", "")
		if status[i] == 1:
			new += " " + i
		else:
			new += " #" + i
	return new


def writestatus(items):
	status = {}
	path = BYOBU_CONFIG_DIR + '/status'
	for i in items:
		status[i[1]] = i[0]
	for key in ["tmux_left", "tmux_right"]:
		try:
			f = open(path, "r")
		except Exception:
			f = open(SHARE + '/status/status', "r")
		lines = f.readlines()
		f.close()
		try:
			f = open(path, "w")
		except Exception:
			f = open(path, "a+")
		for l in lines:
			if l.startswith("%s=" % key):
				val = genstatusstring(key, status)
				f.write("%s=\"%s\"\n" % (key, val))
			else:
				f.write(l)
		f.close


def togglestatus(snackScreen, size):
	itemlist = readstatus()
	rl = Label("")
	r = CheckboxTree(12, scroll=1)
	count = 0
	for item in itemlist:
		if item[0] != -1:
			r.append(item[1], count, selected=item[0])
		count = count + 1
	bb = ButtonBar(snackScreen, ((_("Apply"), "apply"), (_("Cancel"), "cancel", ESC)), compact=1)
	g = GridForm(snackScreen, _("Toggle status notifications"), 2, 4)
	g.add(rl, 0, 0, anchorLeft=1, anchorTop=1, padding=(4, 0, 0, 1))
	g.add(r, 1, 0)
	g.add(bb, 1, 1, padding=(4, 1, 0, 0))
	if bb.buttonPressed(g.runOnce()) != "cancel":
		count = 0
		for item in itemlist:
			if item[0] != -1:
				item[0] = r.getEntryValue(count)[1]
			count = count + 1
		writestatus(itemlist)
		reload_required()
	return 100


def install(snackScreen, size, isInstalled):
	out = ""
	if isInstalled:
		if subprocess.call(["byobu-launcher-uninstall"]) == 0:
			out = _("Byobu will not be launched next time you login.")
		button = messagebox(snackScreen, 60, 2, _("Message"), out, buttons=((_("Menu"), )))
		return 101
	else:
		if subprocess.call(["byobu-launcher-install"]) == 0:
			out = _("Byobu will be launched automatically next time you login.")
		button = messagebox(snackScreen, 60, 2, "Message", out, buttons=((_("Menu"), )))
		return 100


def appendtofile(p, s):
	f = open(p, 'a')
	try:
		f.write(s)
	except IOError:
		f.close()
		return
	f.close()
	return


def getesckey():
	line = ""
	path = BYOBU_CONFIG_DIR + '/keybindings.tmux'
	if os.path.exists(path):
		for l in open(path):
			if l.startswith("set -g prefix "):
				line = l
	else:
		return DEF_ESC
	if line == "":
		return DEF_ESC
	esc = line[line.find('^') + 1]
	if esc == "`":
		esc = " "
	return esc


def setesckey(key):
	if key.isalpha():
		# throw away outputs in order that the view isn't broken
		nullf = open(os.devnull, "w")
		subprocess.call(["byobu-ctrl-a", "screen", key], stdout=nullf)
		nullf.close()


def chgesc(snackScreen, size):
	esc = Entry(2, text=getesckey(), returnExit=1)
	escl = Label(_("Escape key: ctrl-"))
	bb = ButtonBar(snackScreen, ((_("Apply"), "apply"), (_("Cancel"), "cancel", ESC)), compact=1)
	g = GridForm(snackScreen, _("Change escape sequence"), 2, 4)
	g.add(escl, 0, 0, anchorLeft=1, padding=(1, 0, 0, 1))
	g.add(esc, 1, 0, anchorLeft=1)
	g.add(bb, 1, 1)
	g.setTimer(100)
	loop = 1
	while loop:
		which = g.run()
		if which == "TIMER":
			val = esc.value()
			if len(val) > 1:
				esc.set(val[1])
			# Ensure that escape sequence is not \ or /
			if val == '/' or val == '\\':
				esc.set(DEF_ESC)
			# Ensure that the escape sequence is not set to a number
			try:
				dummy = int(esc.value())
				esc.set(DEF_ESC)
			except Exception:
				# do nothing
				dummy = "foo"
		else:
			loop = 0
	snackScreen.popWindow()
	button = bb.buttonPressed(which)
	if button != "cancel":
		setesckey(esc.value())
		reload_required()
		if button == "exit":
			return 0
	return 100


def autolaunch():
	if os.path.exists(BYOBU_CONFIG_DIR + "/disable-autolaunch"):
		return 0
	try:
		for line in open("%s/.profile" % HOME):
			if "byobu-launch" in line:
				return 1
	except Exception:
		return 0
	if os.path.exists("/etc/profile.d/Z97-%s.sh" % PKG):
		return 1
	return 0


def main():
	"""This is the main loop of our utility"""
	size = terminal_size()
	snackScreen = SnackScreen()
	snackScreen.drawRootText(1, 0, _('Byobu Configuration Menu'))
	snackScreen.pushHelpLine(_('<Tab> between elements | <Enter> selects | <Esc> exits'))
	isInstalled = autolaunch()
	tag = 100
	while tag > 0:
		tag = menu(snackScreen, size, isInstalled)
		if tag == 1:
			tag = help(snackScreen, size)
		elif tag == 2:
			tag = togglestatus(snackScreen, size)
		elif tag == 3:
			tag = chgesc(snackScreen, size)
		elif tag == 4:
			tag = install(snackScreen, size, isInstalled)
			isInstalled = autolaunch()
	snackScreen.finish()
	sys.exit(0)


if __name__ == "__main__":
	main()
