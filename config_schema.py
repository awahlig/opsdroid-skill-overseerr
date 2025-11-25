from voluptuous import (Schema, All, Optional, Required, Length, Url,
                        Boolean, ALLOW_EXTRA, MultipleInvalid)


# Not using opsdroid's CONFIG_SCHEMA feature because as of opsdroid 0.28.0,
# the error messages are confusing for schemas with sub-dictionaries.
# (when room.x.url is missing, it's reporting that "room" is missing)


STR_NONEMPTY = All(
    str,
    Length(min=1)
)

CONFIG_SCHEMA = Schema({
    # What's this bot called? Defaults to "opsdroid".
    Required("bot-name", default="opsdroid"): STR_NONEMPTY,

    # The external URL of the Opsdroid web server.
    # Used for Plex auth callbacks and notifications.
    Required("bot-url"): Url(),

    # List of Overseerr servers.
    Required("servers", default=[]): [{
        # The URL of the server (without /api).
        Required("url"): Url(),

        # API key of the server. Optional.
        Optional("api-key"): STR_NONEMPTY,

        # List of rooms that can access this server.
        Required("rooms"): [STR_NONEMPTY],

        # List of rooms that receive webhook notifications. Optional.
        # <bot-url>/skill/overseerr/notification
        Optional("notify-rooms", default=[]): [STR_NONEMPTY],
    }],
}, extra=ALLOW_EXTRA)


def validate(config):
    try:
        return CONFIG_SCHEMA(config)
    except MultipleInvalid as error:
        raise RuntimeError(f"skill-overseerr config validation failed: {error}")
