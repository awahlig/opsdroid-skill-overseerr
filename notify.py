import logging

from opsdroid.events import Message, Image

from voluptuous import Schema, Any, Required, Url, ALLOW_EXTRA, MultipleInvalid

from .api import OverseerrError


NOTIFICATION_TYPE = Any(
    "MEDIA_PENDING",
    "MEDIA_DECLINED",
    "MEDIA_APPROVED",
    "MEDIA_AVAILABLE",
    "ISSUE_CREATED",
    "ISSUE_REOPENED",
    "ISSUE_RESOLVED",
    "ISSUE_COMMENT",
)

MEDIA_STATUS = Any(
    "UNKNOWN",
    "PENDING",
    "PROCESSING",
    "PARTIALLY_AVAILABLE",
    "AVAILABLE",
)

# https://docs.overseerr.dev/using-overseerr/notifications/webhooks#template-variables
# As of 23.11.2025
NOTIFICATION_SCHEMA = Schema({
    Required("notification_type"): NOTIFICATION_TYPE,
    Required("subject"): str,
    Required("message"): str,
    Required("image"): Any("", Url()),
    Required("email"): str,
    Required("username"): str,
    Required("media"): Any(None, {
        Required("media_type"): Any("movie", "tv"),
        Required("tmdbId"): str,
        Required("imdbId"): str,
        Required("tvdbId"): str,
        Required("status"): MEDIA_STATUS,
    }),
    Required("extra"): [{
        Required("name"): str,
        Required("value"): str,
    }],
    Required("request"): Any(None, {
        Required("request_id"): str,
        Required("requestedBy_email"): str,
        Required("requestedBy_username"): str,
    }),
    Required("issue"): Any(None, {
        Required("issue_id"): str,
        Required("reportedBy_username"): str,
    }),
    Required("comment"): Any(None, {
        Required("comment_message"): str,
        Required("commentedBy_username"): str,
    }),
}, extra=ALLOW_EXTRA)

logger = logging.getLogger(__name__)


def validate_notification(data):
    logger.debug("Validating notification: %s", data)

    try:
        return NOTIFICATION_SCHEMA(data)
    except MultipleInvalid as error:
        logger.exception("Error parsing notification data")
        return None


async def send_notification(opsdroid, room, data):
    api = room.admin_api

    extra_map = {item["name"]: item["value"]
                 for item in data["extra"]}

    media = data["media"]
    if media:
        try:
            async with api.new_session() as session:
                ratings = await session.get_ratings(
                    media["media_type"],
                    media["tmdbId"])
        except OverseerrError:
            logger.exception("Error retrieving ratings for %s", media)
            ratings = {}
    else:
        ratings = {}

    async with room.notify_lock:
        if data["image"]:
            await opsdroid.send(Image(
                name=data["subject"],
                url=data["image"],
                target=room.name))

        tmpl = room.jinja.get_template("notify.jinja")
        text = await tmpl.render_async(data, api=api,
                                       ratings=ratings,
                                       extra_map=extra_map)
        await opsdroid.send(Message(text, target=room.name))
