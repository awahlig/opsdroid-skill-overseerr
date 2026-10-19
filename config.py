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

        # API key of the server.
        Optional("api-key", default=""): STR_NONEMPTY,

        # Optional: fetch notification ratings from a different API
        # server than this one -- e.g. Rutter, which serves the same
        # /{media_type}/{tmdbId}/ratings endpoint under its own host
        # and API key while this server is a legacy instance being
        # migrated away from. Defaults to this server when unset.
        Optional("ratings-url"): Url(),
        Optional("ratings-api-key", default=""): STR_NONEMPTY,

        # List of admins that access this server using the API key.
        Optional("admins", default=[]): [STR_NONEMPTY],

        # List of users that can access this server by logging into
        # their account using Plex.
        Optional("users", default=[]): [STR_NONEMPTY],

        # List of rooms where this server can be accessed.
        # The participants will need to be in either "users" or "admins".
        # These rooms also receive notifications.
        Optional("rooms", default=[]): [STR_NONEMPTY],
    }],
}, extra=ALLOW_EXTRA)


def validate(config):
    try:
        return CONFIG_SCHEMA(config)
    except MultipleInvalid as error:
        raise RuntimeError(f"skill-overseerr config validation failed: {error}")
