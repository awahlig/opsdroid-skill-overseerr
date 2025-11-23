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
    Required("bot-name", default="opsdroid"): STR_NONEMPTY,
    Required("bot-url"): Url(),
    Required("rooms", default={}): {
        STR_NONEMPTY: All(
            # For str, convert to dict first
            lambda v: { "url": v } if isinstance(v, str) else v,
            {
                Required("url"): Url(),
                Optional("more-rooms", default=[]): [STR_NONEMPTY],
                Optional("api-key"): STR_NONEMPTY,
                Optional("notify", default=False): Boolean(),
            }
        ),
    },
}, extra=ALLOW_EXTRA)


def validate(config):
    try:
        return CONFIG_SCHEMA(config)
    except MultipleInvalid as error:
        raise RuntimeError(f"skill-overseerr config validation failed: {error}")
