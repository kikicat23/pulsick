#!/usr/bin/env python3

# pulsick, by kikicat, 2023
# automate Ivanti / Pulse Secure log-in on Linux

# inspired from:
# * pyautogui X11 source code from Al Sweigart
#   https://github.com/asweigart/pyautogui/blob/master/pyautogui/_pyautogui_x11.py
# * x11_watch_active_window.py from Stephan Sokolow
#   https://gist.github.com/ssokolow/e7c9aae63fb7973e4d64cff969a78ae8

from contextlib import contextmanager
from typing import Any, Dict, Optional, Tuple, Union  # noqa

from Xlib import X, XK
from Xlib.display import Display
from Xlib.error import XError
from Xlib.xobject.drawable import Window
from Xlib.protocol.rq import Event
from Xlib.ext.xtest import fake_input

from logging import info, debug
import time
import logging
import subprocess
import argparse

class Xorg(object):
	LETTERMAP = {
			' ': 'space',
			'space': 'space',
			'\t': 'Tab',
			'\n': 'Return',
			'\r': 'Return',
			'\e': 'Escape',
			'!': 'exclam',
			'#': 'numbersign',
			'%': 'percent',
			'$': 'dollar',
			'&': 'ampersand',
			'"': 'quotedbl',
			"'": 'apostrophe',
			'(': 'parenleft',
			')': 'parenright',
			'*': 'asterisk',
			'=': 'equal',
			'+': 'plus',
			',': 'comma',
			'-': 'minus',
			'.': 'period',
			'/': 'slash',
			':': 'colon',
			';': 'semicolon',
			'<': 'less',
			'>': 'greater',
			'?': 'question',
			'@': 'at',
			'[': 'bracketleft',
			']': 'bracketright',
			'\\': 'backslash',
			'^': 'asciicircum',
			'_': 'underscore',
			'`': 'grave',
			'{': 'braceleft',
			'|': 'bar',
			'}': 'braceright',
			'~': 'asciitilde',
	}

	def __init__(self):
		# Connect to the X server and get the root window
		self.disp = Display()
		self.root = self.disp.screen().root

		# Prepare the property names we use so they can be fed into X11 APIs
		self.NET_ACTIVE_WINDOW = self.disp.intern_atom('_NET_ACTIVE_WINDOW')
		self.NET_WM_NAME = self.disp.intern_atom('_NET_WM_NAME')  # UTF-8
		self.WM_NAME = self.disp.intern_atom('WM_NAME')           # Legacy encoding

		self.last_seen = {'xid': None, 'title': None}  # type: Dict[str, Any]
		self.get_window_name(self.get_active_window()[0])

	def kbd_letter(self, c):
		debug("kbd_letter: %s" % c)
		shift = self.letter_need_shift(c)
		if shift:
			fake_input(self.disp, X.KeyPress, self.keycode('Shift_L'))
		c = self.letter_map(c)
		ksym=XK.string_to_keysym(c)
		kcode=self.disp.keysym_to_keycode(ksym)
		fake_input(self.disp, X.KeyPress, kcode)
		fake_input(self.disp, X.KeyRelease, kcode)
		if shift:
			fake_input(self.disp, X.KeyRelease, self.keycode('Shift_L'))
		self.disp.sync()

	def kbd_string(self, s):
		debug("kbd_string: %s" % s)
		for c in s:
			self.kbd_letter(c)

	def kbd_special(self, c):
		debug("kbd_special: %s" % c)
		fake_input(self.disp, X.KeyPress, self.keycode(c))
		fake_input(self.disp, X.KeyRelease, self.keycode(c))
		self.disp.sync()

	def wait_windowchange(self):
		# Listen for _NET_ACTIVE_WINDOW changes
		self.root.change_attributes(event_mask=X.PropertyChangeMask)

		while True:  # next_event() sleeps until we get an event
			event = self.disp.next_event()

			"""Handler for X events which ignores anything but focus/title change"""
			if event.type != X.PropertyNotify:
				continue # loop if no interesting event

			changed = False
			if event.atom == self.NET_ACTIVE_WINDOW:
				if self.get_active_window()[1]:
					self.get_window_name(self.last_seen['xid'])  # Rely on the side-effects
					changed = True
			elif event.atom in (self.NET_WM_NAME, self.WM_NAME):
				changed = changed or self.get_window_name(self.last_seen['xid'])[1]

			if changed:
				return self.last_seen

	def letter_need_shift(self, c):
		return c.isupper() or c in set('~!@#$%^&*()_+{}|:"<>?')

	def letter_map(self, c):
		if c in self.LETTERMAP:
			return self.LETTERMAP[c]
		return c

	def keycode(self, s):
		return self.disp.keysym_to_keycode(XK.string_to_keysym(s))

	@contextmanager
	def window_obj(self, win_id: Optional[int]) -> Window:
		"""Simplify dealing with BadWindow (make it either valid or None)"""
		window_obj = None
		if win_id:
			try:
				window_obj = self.disp.create_resource_object('window', win_id)
			except XError:
				pass
		yield window_obj

	def get_active_window(self) -> Tuple[Optional[int], bool]:
		"""Return a (window_obj, focus_has_changed) tuple for the active window."""
		response = self.root.get_full_property(self.NET_ACTIVE_WINDOW,
										  X.AnyPropertyType)
		if not response:
			return None, False
		win_id = response.value[0]

		focus_changed = (win_id != self.last_seen['xid'])
		if focus_changed:
			with self.window_obj(self.last_seen['xid']) as old_win:
				if old_win:
					old_win.change_attributes(event_mask=X.NoEventMask)

			self.last_seen['xid'] = win_id
			with self.window_obj(win_id) as new_win:
				if new_win:
					new_win.change_attributes(event_mask=X.PropertyChangeMask)

		return win_id, focus_changed

	def _get_window_name_inner(self, win_obj: Window) -> str:
		"""Simplify dealing with _NET_WM_NAME (UTF-8) vs. WM_NAME (legacy)"""
		for atom in (self.NET_WM_NAME, self.WM_NAME):
			try:
				window_name = win_obj.get_full_property(atom, 0)
			except UnicodeDecodeError:  # Apparently a Debian distro package bug
				title = "<could not decode characters>"
			else:
				if window_name:
					win_name = window_name.value  # type: Union[str, bytes]
					if isinstance(win_name, bytes):
						# Apparently COMPOUND_TEXT is so arcane that this is how
						# tools like xprop deal with receiving it these days
						win_name = win_name.decode('latin1', 'replace')
					return win_name
				else:
					title = "<unnamed window>"

		return "{} (XID: {})".format(title, win_obj.id)

	def get_window_name(self, win_id: Optional[int]) -> Tuple[Optional[str], bool]:
		"""Look up the window name for a given X11 window ID"""
		if not win_id:
			self.last_seen['title'] = None
			return self.last_seen['title'], True

		title_changed = False
		with self.window_obj(win_id) as wobj:
			if wobj:
				try:
					win_title = self._get_window_name_inner(wobj)
				except XError:
					pass
				else:
					title_changed = (win_title != self.last_seen['title'])
					self.last_seen['title'] = win_title

		return self.last_seen['title'], title_changed

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="automate Ivanti / Pulse Secure log-in on Linux")
	parser.add_argument('-v', '--verbose', action='store_const', dest="loglevel", const=logging.DEBUG, default=logging.INFO)
	parser.add_argument('login', help='Login')
	parser.add_argument('password_cmd', help='Command to execute to get password')
	parser.add_argument('otp_cmd', help='Command to execute to get OTP')
	args = parser.parse_args()

	logging.basicConfig(level=args.loglevel)

	xorg = Xorg()
	win = xorg.last_seen
	while True:
		info("windowchange: %s" % win)
		if win['title'] == 'Pulse Secure': # main UI
			pass
		elif win['title'] == 'pulseUI': # probably log-in prompt
			debug("pulse_login BEGIN %s" % time.strftime("%Y%m%d_%H%M%S"))
			time.sleep(3)

			xorg.kbd_string(args.login)
			xorg.kbd_special("Tab")
			time.sleep(0.5)

			password = subprocess.run(args.password_cmd, shell=True, capture_output=True).stdout.decode()
			debug("password: %s" % password)
			xorg.kbd_string(password)
			xorg.kbd_special("Return")
			time.sleep(3)

			otp = subprocess.run(args.otp_cmd, shell=True, capture_output=True).stdout.decode()
			debug("otp: %s" % password)
			xorg.kbd_string(otp)
			xorg.kbd_special("Return")
			time.sleep(1)

			debug("pulse_login END %s" % time.strftime("%Y%m%d_%H%M%S"))
		debug("windowchange done")
		win = xorg.wait_windowchange()
