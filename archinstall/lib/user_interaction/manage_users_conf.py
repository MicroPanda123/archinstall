from __future__ import annotations

import logging
import re
from typing import Any, Dict, TYPE_CHECKING, List

from ..menu import Menu
from ..menu.list_manager import ListManager
from ..output import log
from ..storage import storage
from .utils import get_password

if TYPE_CHECKING:
	_: Any


class UserList(ListManager):
	"""
	subclass of ListManager for the managing of user accounts
	"""

	def __init__(self, prompt: str, lusers: dict, sudo: bool = None):
		"""
		param: prompt
		type: str
		param: lusers dict with the users already defined for the system
		type: Dict
		param: sudo. boolean to determine if we handle superusers or users. If None handles both types
		"""
		self.sudo = sudo
		self.actions = [
			str(_('Add a user')),
			str(_('Change password')),
			str(_('Promote/Demote user')),
			str(_('Delete User'))
		]
		super().__init__(prompt, lusers, self.actions, self.actions[0])

	def reformat(self, data: List) -> Dict:
		def format_element(elem :str):
			# secret gives away the length of the password
			pwd = '*' * 16 if data[elem].get('!password') else ''
			super_user = 'Superuser' if data[elem].get('sudoer') else ' '
			return f"{elem:16}: password {pwd:16} {super_user}"

		return {format_element(e): e for e in data}

	def action_list(self):
		active_user = list(self.target.keys())[0] if self.target else None
		sudoer = self.target[active_user].get('sudoer', False)
		if self.sudo is None:
			return self.actions
		if self.sudo and sudoer or not self.sudo and not sudoer:
			return self.actions
		else:
			return [self.actions[2]]

	def exec_action(self, data: Any):
		active_user = list(self.target.keys())[0] if self.target else None
		if self.action == self.actions[0]:  # add
			new_user = self.add_user()
			# no unicity check, if exists will be replaced
			data.update(new_user)
		elif self.action == self.actions[1]:  # change password
			data[active_user]['!password'] = get_password(
				prompt=str(_('Password for user "{}": ').format(active_user)))
		elif self.action == self.actions[2]:  # promote/demote
			data[active_user]['sudoer'] = not data[active_user]['sudoer']
		elif self.action == self.actions[3]:  # delete
			del data[active_user]

	def _check_for_correct_username(self, username: str) -> bool:
		if re.match(r'^[a-z_][a-z0-9_-]*\$?$', username) and len(username) <= 32:
			return True
		log("The username you entered is invalid. Try again", level=logging.WARNING, fg='red')
		return False

	def add_user(self):
		print(_('\nDefine a new user\n'))
		prompt = str(_("User Name : "))
		while True:
			userid = input(prompt).strip(' ')
			if not userid:
				return {}  # end
			if self._check_for_correct_username(userid):
				break
		if self.sudo:
			sudoer = True
		elif self.sudo is not None:
			sudoer = False
		else:
			sudoer = False
			sudo_choice = Menu(str(_('Should {} be a superuser (sudoer)?')).format(userid), Menu.yes_no(),
								skip=False,
								preset_values=Menu.yes() if sudoer else Menu.no(),
								default_option=Menu.no()).run()
			sudoer = sudo_choice == Menu.yes()

		password = get_password(prompt=str(_('Password for user "{}": ').format(userid)))

		return {userid: {"!password": password, "sudoer": sudoer}}


def manage_users(prompt: str, sudo: bool) -> tuple[dict, dict]:
	# TODO Filtering and some kind of simpler code
	lusers = {}
	if storage['arguments'].get('!superusers', {}):
		lusers |= {
		    uid: {
		        '!password':
		        storage['arguments']['!superusers'][uid].get('!password'),
		        'sudoer': True,
		    }
		    for uid in storage['arguments'].get('!superusers', {})
		}
	if storage['arguments'].get('!users', {}):
		lusers |= {
		    uid: {
		        '!password': storage['arguments']['!users'][uid].get('!password'),
		        'sudoer': False,
		    }
		    for uid in storage['arguments'].get('!users', {})
		}
	# processing
	lusers = UserList(prompt, lusers, sudo).run()
	# return data
	superusers = {
		uid: {
			'!password': lusers[uid].get('!password')
		}
		for uid in lusers if lusers[uid].get('sudoer', False)
	}
	users = {uid: {'!password': lusers[uid].get('!password')} for uid in lusers if not lusers[uid].get('sudoer', False)}
	storage['arguments']['!superusers'] = superusers
	storage['arguments']['!users'] = users
	return superusers, users


def ask_for_superuser_account(prompt: str) -> Dict[str, Dict[str, str]]:
	prompt = prompt or str(_('Define users with sudo privilege, by username: '))
	superusers, dummy = manage_users(prompt, sudo=True)
	return superusers


def ask_for_additional_users(prompt: str = '') -> Dict[str, Dict[str, str | None]]:
	prompt = prompt or _(
	    'Any additional users to install (leave blank for no users): ')
	dummy, users = manage_users(prompt, sudo=False)
	return users
