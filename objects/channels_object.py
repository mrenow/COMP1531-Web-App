from datetime import datetime, timedelta
from .messages import Message
from server.state import *
from server.constants import *

'''
get_channels
'''

class Channel:
	def __init__(self, name, owner_id, is_public):
		if len(name) > 20:
			raise ValueError("Name cannot be over 20 characters")
		self._name = name
		self._owners_set = set([owner_id])
		self._members_set = set([owner_id])
		self._is_public = is_public
		self._id = num_channels()

		# Functions as the entire standup
		self._standup_message_id = None

		# Message list contains message_id
		self._message_list = []

		set_channel(self._id, self)
		get_user(owner_id).get_channels().add(self._id)
		get_user(owner_id).get_owner_channels().add(self._id)
		inc_channels()

	def set_is_public(self, is_public):
		self._is_public = is_public

	def get_name(self):
		return self._name

	def get_owners(self):
		return self._owners_set

	def get_members(self):
		return self._members_set

	def get_is_public(self):
		return self._is_public

	def get_id(self):
		return self._id

	def get_message_list(self):
		return self._message_list

	def get_num_messages(self):
		return len(self._message_list)

	def send_message(self, message_id):
		self._message_list.append(message_id)
		get_message(message_id).send()

		return message_id

	def standup_active(self):
		# Check if a standup is currently active
		return self._standup_message_id != None and not get_message(self._standup_message_id).is_sent()

	def standup_start(self, u_id, duration_seconds):
		if self.standup_active():
			raise ValueError(f"Standup already active in channel {self._name}.")
		if duration_seconds > MAX_STANDUP_SECONDS:
			raise ValueError(
				f"Standup duration ({duration_seconds}s) exceeds maximum ({MAX_STANDUP_SECONDS}s).")
		# FIX COMMENT
		# Overwrite old standup message with new unsent message.
		time_finish = datetime.now(TIMEZONE) + timedelta(seconds=duration_seconds)
		new_message =  Message(STANDUP_START_STR, self._id, u_id, time=time_finish, is_standup=True)
		self._standup_message_id = new_message.get_id()
		return time_finish

	def standup_send(self, u_id, text):
		if not self.standup_active():
			raise ValueError(f"No standup active in channel {self._name}")
		if MAX_MESSAGE_LEN < len(text):
			raise ValueError(
				f"Message '{text[:10]}...' with length {len(text)} exceeds maximum allowable length {MAX_MESSAGE_LEN}.")

		full_text = f"\n{get_user(u_id).get_name_first()}: {text}"
		message = get_message(self._standup_message_id)

		# Append full_text to standup message.
		message.set_message(message.get_message() + full_text)



	'''
	Returns the completion datetime of the last standup initiated on the channel.
	Returns earliest possible time if no standup has been initiated.
	'''

	def standup_time(self):
		# Return earliest possible time if no standup has ever been initiated
		if self._standup_message_id == None:
			return datetime.min
		else:
			return get_message(self._standup_message_id).get_time()

	def channel_messages(self, start, u_id):
		return [get_message(mess).to_json(u_id) for mess in self._message_list[-(start+1) : -(start+51) : -1]]

	def delete_message(self, message_id):
		for index, entry in enumerate(self._message_list):
			if message_id == entry:
				del self._message_list[index]
				return
		ValueError(f"Message {message_id} not found")

	def join(self, u_id):
		self._members_set.add(u_id)
		get_user(u_id).get_channels().add(self._id)
		

	def to_json_members(self):
		return dict(name=self._name,
                    owner_members=[get_user(u_id).to_json() for u_id in self._owners_set],
                    all_members=[get_user(u_id).to_json() for u_id in self._members_set])

	def to_json_id(self):
		return dict(name=self._name,
                    channel_id=self._id)

	def leave(self, u_id):
		self._members_set.discard(u_id)
		# Leaving a channel also removes owner status
		if u_id in self._owners_set:
			self._owners_set.discard(u_id)
		get_user(u_id).get_channels().discard(self._id)

	def add_owner(self, u_id):
		if u_id in self._owners_set:
			raise ValueError(
				f"User {u_id} is already an owner of channel {self._id}")
		self._owners_set.add(u_id)
		get_user(u_id).get_channels().add(self._id)
		self.join(u_id)

	def remove_owner(self, u_id):
		if u_id not in self._owners_set:
			raise ValueError(
				f"User {u_id} is not an owner of channel {self._id}")
		self._owners_set.discard(u_id)
