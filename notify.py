import logging
import re

from opsdroid.events import Message, Image

from voluptuous import (Schema, Any, Optional, Required, Url,
                        ALLOW_EXTRA, MultipleInvalid)

from .api import OverseerrError


NOTIFICATION_TYPE = Any(
    "TEST_NOTIFICATION",
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

# https://docs.seerr.dev/using-seerr/notifications/webhook/#template-variables
# As of 18.10.2026
NOTIFICATION_SCHEMA = Schema({
    # General
    Required("notification_type"): NOTIFICATION_TYPE,
    Optional("event", default=""): str,
    Required("subject"): str,
    Required("message"): str,
    Required("image"): Any("", Url()),
    # Notify User
    Required("email"): str,
    Required("username"): str,
    # Special
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

# Placeholders in the "Link Template" extra item, e.g. <tmdbId>.
LINK_PLACEHOLDER = re.compile(r"<(\w+)>")

logger = logging.getLogger(__name__)


def validate_notification(data):
    logger.debug("Validating notification: %s", data)

    try:
        return NOTIFICATION_SCHEMA(data)
    except MultipleInvalid as error:
        logger.exception("Error parsing notification data")
        return None


def make_media_url(api, media, extra_map):
    # Links point to the server by default. A "Link Template" extra item,
    # e.g. "https://example.com/title/movie/<tmdbId>", overrides this,
    # with the placeholders filled in from the media fields.
    template = extra_map.get("Link Template")
    if not template:
        return api.make_abs_url(f"/{media['media_type']}/{media['tmdbId']}")
    return LINK_PLACEHOLDER.sub(
        lambda match: media.get(match.group(1), match.group(0)),
        template)


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
        media_url = make_media_url(api, media, extra_map)
    else:
        ratings = {}
        media_url = None

    async with room.notify_lock:
        if data["image"]:
            await opsdroid.send(Image(
                name=data["subject"],
                url=data["image"],
                target=room.name))

        tmpl = room.jinja.get_template("notify.jinja")
        text = await tmpl.render_async(data, api=api,
                                       ratings=ratings,
                                       media_url=media_url,
                                       extra_map=extra_map)
        await opsdroid.send(Message(text, target=room.name))
