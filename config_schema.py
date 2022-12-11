from voluptuous import (Schema, All, Any, Required, Length, Url,
                        ALLOW_EXTRA, MultipleInvalid)


# Not using opsdroid's CONFIG_SCHEMA feature because as of opsdroid 0.28.0,
# the error messages are confusing for schemas with sub-dictionaries.
# (when room.x.url is missing, it's reporting that "room" is missing)


str_nonempty = All(str, Length(min=1))
schema = Schema({
    Required("bot-name", default="opsdroid"): str_nonempty,
    Required("bot-url"): Url(),
    Required("rooms", default={}): {
        str_nonempty: Any(Url(), {
            Required("url"): Url(),
            Required("more-rooms", default=[]): [str_nonempty],
            "api-key": str_nonempty,
        }),
    },
    "notify-room": str_nonempty,
}, extra=ALLOW_EXTRA)


def validate(config):
    try:
        return schema(config)
    except MultipleInvalid as error:
        raise RuntimeError(f"skill-overseerr config validation failed: {error}")
