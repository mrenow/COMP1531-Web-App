import sys
from json import dumps
from flask import Flask, request
from datetime import datetime, timedelta
from multiprocessing import Lock
from typing import List, Dict
from server.AccessError import AccessError
import re # used for checking email formating
regex = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$' # ''
import jwt

# 
# CONSTANTS 
#

ADMIN = 2
MEMBER = 3
OWNER = 1

MAX_STANDUP_SECONDS = 60*15
MAX_MESSAGE_LEN = 1000
STANDUP_START_STR = "Standup results."

private_key = "secure password"

users = {} # u_id: user obj
channels = {} # chann
messages = {} # message_id: message obj

messages_to_send_lock = Lock()
messages_to_send = [] 

active_standup = False

num_messages = 0
user_count = 0
num_channels = 0
tokcount = 0
valid_toks = set()


TEST_INVALID_MESSAGE = "0"*1001
TEST_VALID_MESSAGE = "0"*1000


def inc_users():
    global user_count
    user_count += 1

def inc_channels():
    global num_channels
    num_channels += 1

def inc_messages():
    global num_messages
    num_messages += 1

def get_num_messages():
    global num_messages
    return num_messages
def get_num_users():
    global user_count
    return user_count
def get_num_channels():
    global num_channels
    return num_channels

def get_channels():
    global channels
    return channels
def get_users():
    global users
    return users
def get_messages():
    global messages
    return messages
def get_messages_to_send():
    global messages_to_send
    return messages_to_send

from objects.messages import Message
from objects.channels_object import Channel
from objects.users_object import User



def reset():
    global users, channels, messages, num_messages, num_channels, user_count
    users = {} # u_id: user obj
    channels = {} # chann
    messages = {} # message_id: message obj
    num_messages = 0
    num_channels = 0
    user_count = 0

# Contains all checks to be done regularly
def update():
    global messages_to_send, messages_to_send_lock
    print("to send", messages_to_send)
    messages_to_send_lock.acquire()
    try:
        for index, m in enumerate(messages_to_send):
            print(m.get_time(), datetime.now())
            if m.get_time() < datetime.now():
                channels[m.get_channel()].send_message(m.get_id())
                del messages_to_send[index]
    # Always release lock please thankyou
    finally:
        messages_to_send_lock.release()

    

    
def check_message_exists(message_id):
    global messages
    if message_id not in messages:
        raise ValueError(f"Message {message_id} does not exist. messages: {messages}")
def check_channel_exists(channel_id):
    global channels
    if channel_id not in channels:
        raise ValueError(f"Channel {channel_id} does not exist. channels: {channels}")
def check_user_exists(user_id):
    global users
    if user_id not in users:
        raise ValueError(f"User {user_id} does not exist. users: {users}")

'''
Raises an Access error if all of the conditions specified are not met.
Usage:
Only allow if is ( owner of channel or admin or particular user ) and in channel:
>>> authcheck(u_id, user = particular_u_id, chowner = channel_id,  admin = True)
>>> authcheck(u_id, user = channel_id) 
'''

def authcheck(u_id, user = None, channel = None, chowner = None, admin = False):

    auth = False 

    if user != None and user == u_id:
        auth = True
    if channel != None and channel in users[u_id].get_channels():
        auth = True
    if chowner != None and u_id in channels[chowner].get_owners():
        auth = True
    if admin and users[u_id].get_permission() in (OWNER,ADMIN): 
        auth = True
    if auth:
        return

    if user != None:
        raise AccessError(f"auth: User {u_id} is not user {user}.")
    if channel != None:
        raise AccessError(f"auth: User {u_id} is not in channel {channel}")
    if chowner != None:
        raise AccessError(f"auth: User {u_id} is not an owner of {channel}.")  
    if admin:
        raise AccessError(f"auth: User {u_id} is not admin")


def tokcheck(token) -> int:   
    
    global valid_toks
    payload = jwt.decode(token, private_key, algorithms= ["HS256"])
    if payload["tok_id"] in valid_toks:
        return payload["u_id"]
    raise ValueError("Invalid Token")

def maketok(u_id) -> str:
    global tokcount 
    global valid_toks
    payload = {"u_id": u_id, "tok_id": tokcount, "time" : str(datetime.now())}
    valid_toks.add(tokcount)
    tokcount += 1
    return jwt.encode(payload, private_key, algorithm= "HS256")

def killtok(token) -> Dict["is_success", bool]:
    global valid_toks
    payload = jwt.decode(token, private_key, algorithms= ["HS256"])
    tokid = payload["tok_id"]
    if payload["tok_id"] in valid_toks:
        valid_toks.remove(payload["tok_id"])
        return dict(is_success = True)
    return dict(is_success = False)



def auth_login(email, password):
    global users
    #Check in users if email exists then try to match the pw
    for user in users.values():
        if user._email == email:
            if user._password == password:        
                return dict(token = maketok(user._u_id), u_id = user._u_id)
            raise ValueError("Wrong Password for Given Email Address")
    raise ValueError("Incorrect Email Login")

    return {}

def auth_logout(token):
    return killtok(token)

def auth_register(email, password, name_first, name_last):
    # Check if email is good
    global regex
    if(not re.search(regex,email)):
        raise ValueError("Invalid Email Address")
    else:
        # Check if email is used by another user
        global users
        print("users:", users)
        for user in users.values():
            if user.get_email() == email:
                raise ValueError("Email already in use")

        # Password
        if len(password) < 6:
            raise ValueError("Password too short")

        # First and last name within 1 and 50 characters
        if len(name_first) > 50:
            raise ValueError("First name is too long")
        if len(name_last) > 50:
            raise ValueError("Last name is too long")
        if len(name_first) < 1:
            raise ValueError("First name is too short")
        if len(name_last) < 1:
            raise ValueError("Last name is too short")
        
        obj = User(name_first, name_last, email, password)
        u_id = obj.get_id()
        users[u_id] = obj
        return dict(token = maketok(u_id), u_id = u_id)

def auth_passwordreset_request(email):
    return {}
def auth_passwordreset_reset(reset_code, new_password):
    return {}
def channel_invite(token, channel_id, u_id):
    requester = tokcheck(token) 
    if channel_id not in channels:
        raise ValueError((f"channel_invite: Channel does not exist."))
    if u_id not in users:
        raise ValueError((f"channel_invite: User does not exist."))
    if requester not in channels[channel_id].get_members():
        raise AccessError((f"auth: User is not a member of this channel"))
    
    channels[channel_id].join(u_id)

    return {}


'''
Raises a value error when channel id does not exist

'''

def channel_details(token, channel_id):
    requester = tokcheck(token)
    if channel_id not in channels:
        raise ValueError((f"channel_invite: Channel does not exist."))
    if requester not in channels[channel_id].get_members():
        raise AccessError((f"auth: User is not a member of this channel"))
    
    return channels[channel_id].details()

def channel_messages(token, channel_id, start):
    requester = tokcheck(token)    
    update()
    check_channel_exists(channel_id)
    
    authcheck(requester, channel = channel_id)
    if start > channels[channel_id].get_num_messages():
        raise ValueError(f"channel_messages: Start index {start} out of bounds on request to channel {channel_id}")

    end = start + 50
    message_list = channels[channel_id].get_message_list()
    if -start-1 < -len(message_list) or -start-51 < -len(message_list):
        end = -1
    return dict(messages = channels[channel_id].channel_messages(start, requester),
            start =  start,
            end = end)

def channel_leave(token, channel_id):
    requester = tokcheck(token)
    if channel_id not in channels:
        raise ValueError((f"channel_invite: Channel does not exist."))
    channels[channel_id].leave(requester)
    return {}

def channel_join(token, channel_id):
    requester = tokcheck(token)
    if channel_id not in channels:
        raise ValueError((f"channel_invite: Channel does not exist."))
    if channels[channel_id].get_is_public() == False:
        raise AccessError("channel is private")
    channels[channel_id].join(requester)
    return {}

def channel_addowner(token, channel_id, u_id):
    requester = tokcheck(token)
    if channel_id not in channels:
        raise ValueError((f"channel_invite: Channel does not exist."))
    authcheck (requester, chowner = channel_id, admin = True)
    if u_id in channels[channel_id].get_owners():
        raise ValueError("User already an owner")
    channels[channel_id].add_owner(u_id)

    return {}

def channel_removeowner(token, channel_id, u_id):
    requester = tokcheck(token)
    if channel_id not in channels:
        raise ValueError((f"channel_invite: Channel does not exist."))
    authcheck (requester, chowner = channel_id, admin = True)
    if u_id not in channels[channel_id].get_owners():
        raise ValueError("User is not an owner")
    channels[channel_id].remove_owner(u_id)

    return {}
def channels_list(token):
    u_id = tokcheck(token)
    channels_list = []
    for x in users[u_id].get_channels():
        #channels_list.append(channels[x].details())
        d = dict(channel_id = channels[x].get_id(),
                 name = channels[x].get_name())
        channels_list.append(d)
    return {"channels": channels_list}

def channels_listall(token):
    u_id = tokcheck(token)
    channels_list = []
    for x in channels.values():
        d = dict(channel_id = x.get_id(),
                 name = x.get_name())
        channels_list.append(d)
    
    return {"channels": channels_list}

def channels_create(token, name, is_public):
    global channels
    u_id = tokcheck(token)
    authcheck(u_id, admin = True)
    
    if len(name) > 20:
        raise ValueError("Name cannot be over 20 characters")
    
    obj = Channel(name, u_id, is_public)
    print("CHANNEL_ID", obj.get_id())
    users[u_id].get_channels().add(obj.get_id())
    channels[obj.get_id()] = obj
    
    return {"channel_id": obj.get_id()}

'''
Added to the specification.
'''

def channels_delete(token, channel_id):
    u_id = tokcheck(token)
    authcheck(u_id, channel = channel_id)
    
    return {}


'''
if message > 1000 chars val error
'''
def message_sendlater(token, channel_id, message, time_sent_millis):
    global channels, messages, messages_to_send
    print("Time: ", time_sent_millis  )
    time_sent = datetime.utcfromtimestamp(time_sent_millis/1000) + timedelta(hours=11)
    print("Time: ", time_sent)


    check_channel_exists(channel_id)

    if time_sent < datetime.now():
        raise ValueError(f"message_sendlater: time is {datetime.now() - time_sent} in the past")
    u_id = tokcheck(token)
    authcheck(u_id, channel = channel_id)
    
    message_obj = Message(message, channel_id, u_id, time_sent)
    print(messages_to_send)
    return {}


'''
Ezra: done
'''
def message_send(token, channel_id, message):
    global channels, messages
    check_channel_exists(channel_id)

    u_id = tokcheck(token)
    authcheck(u_id, channel = channel_id)
    
    message_obj = Message(message, channel_id, u_id)

    return {}

'''
Ezra: done 
'''
def message_remove(token, message_id):
    check_message_exists(message_id)

    u_id = tokcheck(token)
    mess = messages[message_id]
    print("    ",messages[message_id].get_message())
    authcheck(u_id, channel = mess.get_channel())
    authcheck(u_id, user = mess.get_user(), chowner = mess.get_channel(), admin = True)
    mess.remove()
    return {}


'''
Ezra: done 
'''
def message_edit(token, message_id, message):
    message = message.strip()
    if not message:
        message_remove(token, message_id)
        return {}
    u_id = tokcheck(token)
    check_message_exists(message_id)
    mess = get_messages()[message_id] 
    authcheck(u_id, channel = mess.get_channel())
    print("owners:",channels[mess.get_channel()].get_owners())
    authcheck(u_id, user = mess.get_user(), chowner = mess.get_channel(), admin = True)
    
    mess.set_message(message)
    return {}

'''
Ezra: done 
'''
def message_react(token, message_id, react_id): 
    u_id = tokcheck(token)
    mess = messages[message_id]
    authcheck(u_id, channel = mess.get_channel())
    ### Iteration 2 only 
    if react_id != 1:
        raise ValueError(f"message_react: React id {react_id} is not valid on message {mess.get_id}: '{mess.get_message()[:10]}...'")
    ###

    if mess.has_react(react_id) and u_id in mess.get_react(react_id).get_users():
        raise ValueError(f"message_react: User {u_id} already has react_id {react_id} on message {mess.get_id()}: '{mess.get_message()[:10]}...'")
    mess.add_react(u_id, react_id)
    
    return {}

'''
Ezra: done 
'''
def message_unreact(token, message_id, react_id):
    u_id = tokcheck(token)
    mess = messages[message_id]
    authcheck(u_id, channel = mess.get_channel())

    if not mess.has_react(react_id):
        raise ValueError(f"message_unreact: React_id {react_id} not on message {mess.get_id()}: '{mess.get_message()[:10]}...'")
       
    if u_id not in mess.get_react(react_id).get_users():
        raise ValueError(f"message_unreact: User {u_id} does not have react_id {react_id} on message {mess.get_id()}: '{mess.get_message()[:10]}...'")
    
    mess.remove_react(u_id, react_id)
    
    return {}

'''
Ezra: done 
'''
def message_pin(token, message_id):        
    u_id = tokcheck(token)
    mess = messages[message_id]
    if mess.is_pinned():
        raise ValueError(f"message_pin: Message {mess.get_id()} '{mess.get_message()[:10]}...' is already pinned.")
  
    authcheck(u_id, chowner = mess.get_channel(), admin = True)
    
    mess.set_pin(True)
    
    return {}

'''
Unpins message.
Value Error:

Access Error:

returns
'''
def message_unpin(token, message_id):   
    u_id = tokcheck(token)
    mess = messages[message_id]
    
    if not mess.is_pinned():
        raise ValueError(f"message_unpin: Message {mess.get_id()} '{mess.get_message()[:10]}...' is not pinned.")
    authcheck(u_id, chowner = mess.get_channel(), admin = True)
    mess.set_pin(False)
    
    return {}
def user_profile(token, u_id):
    # Check for authorisation
    user_id = tokcheck(token)
    authcheck(user_id)
    # Check for valid user
    global users
    if u_id not in users: 
        raise ValueError("Invalid User id or User does not exist")    
    user = users[u_id]
    return dict(
        email = user.get_email(),
        name_first = user.get_name_first(),
        name_last = user.get_name_last(),
        handle_str = user.get_handle_str())

  
def user_profile_setname(token, name_first, name_last):
    # Check for authorisation
    user_id = tokcheck(token)
    authcheck(user_id)
    # Check if first and last names are within length restrictions otherwise return a ValueError
    if len(name_first) > 50: 
        raise ValueError("First name provided is too long")
    if len(name_last) > 50: 
        raise ValueError("Last name provided is too long")
    if len(name_first) < 1: 
        raise ValueError("First name provided is too short")
    if len(name_last) < 1: 
        raise ValueError("Last name provided is too short")
    
    users[user_id].set_name_first(name_first)
    users[user_id].set_name_last(name_last)
    
    return {}
def user_profile_setemail(token, email):
    # Check for authorisation
    user_id = tokcheck(token)
    authcheck(user_id)
    # Check if email is in correct format
    global regex
    if(re.search(regex,email)):  
        global users
        # Check for email address duplicates
        for user in users.values():
            # Do not raise error if user does not change field
            if user.get_id() != user_id and user._email == email:
                raise ValueError("Email already in use")

        users[user_id].set_email(email)
    
    else:  
        raise ValueError("Invalid Email Address")

    return {}
def user_profile_sethandle(token, handle_str):
    # Check for authorisation
    user_id = tokcheck(token)
    authcheck(user_id)
    # Check if handle str is the right len
    if len(handle_str) > 20:
        raise ValueError("Handle name is too long")  
    if len(handle_str) < 3:
        raise ValueError("Handle name is too short")
    # Check if handle str is already in use by another user
    global users
    for user in users.values():
        # Do not raise error if user keeps their own name unchanged
        if user.get_id() != user_id and user._handle_str == handle_str:

            raise ValueError("Handle name already in use")
    users[user_id].set_handle_str(handle_str)
    

    return {}

def user_profiles_uploadphoto(token, img_url, x_start, y_start, x_end, y_end):
    return {}

def standup_start(token, channel_id, length):
    global channels
    u_id = tokcheck(token)
    check_channel_exists(channel_id)
    authcheck(u_id, channel = channel_id)

    # Raises an error if standup already active
    time_finish = channels[channel_id].standup_start(u_id, length)


    return dict(time_finish = time_finish)

def standup_send(token, channel_id, message):
    global channels
    u_id = tokcheck(token)
    check_channel_exists(channel_id)
    authcheck(u_id, channel = channel_id)
    channels[channel_id].standup_send(u_id, message)

    return {}

def standup_active(token, channel_id):
    global channels
    u_id = tokcheck(token)
    check_channel_exists(channel_id)
    
    is_active = channels[channel_id].standup_active()
    time_finish = channels[channel_id].standup_time() if is_active else None
    
    return dict(is_active = is_active,
                time_finish = time_finish.timestamp() if time_finish else time_finish)


def search(token, query_str):
    return {}
    
def admin_userpermission_change(token, u_id, permission_id):
    user_id = tokcheck(token)
    authcheck(user_id, admin = True)
    if u_id not in users:
        raise ValueError((f"channel_invite: User does not exist."))
    if permission_id not in (OWNER, ADMIN, MEMBER):
        raise ValueError("Permission ID not valid")
    users[u_id].set_permission(permission_id)
    return {}

def relevance_score(string):
    return 1
    
def sort_message(msg_list):
    msg_list.sort(key = relevance_score)
    return msg_list



# { react_id, u_ids, is_this_user_reacted } datetime










