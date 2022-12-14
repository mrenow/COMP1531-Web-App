# Assumptions:


## Raised Errors

* Value error takes priority over access error

* Then token is used after invalidation a AccessError would be returned

* Message_edit throws an access error when the users are not allowed to edit, and a value error on bad message_id or when the edit is over 1000 characters

* Message_send throws value error on bad channel_id

* If a user tries to send messages to a channel they are not in an AccessError is raised. If a user tries to edit, pin, or react a message in a channel they If a standup is already in session, starting another on the channel will raise a value error

## Channels


* The details of a channel includes who has moderation rights of that channel, some sort of description of what the channel is for.

* You can edit the channel name after creating it.

* Channel creators automatically becomes a member of a channel

* Only the server owner can create channels.

* There is a function to delete channels

* The owner of the server is listed as first owner of channel upon creation function.

## Users

* Creation of an account requires a working email that can be verified right away.

* Token is always valid after a successful login and only invalidated after logout

* One user can have multiple valid session tokens simultaneously.

* Member lists are of the userIDs.

* The profile picture that users can upload has certain size and potentially profanity constraints.

## Messaging

* When chatting, certain words may be banned or appear as **** if a language filter is in place.

* Channel owners can also pin messages

* React Id is a function of the react type and the user id

* Messages are listed in order from latest to earliest

## Misc

* Ids are positive integers or 0
