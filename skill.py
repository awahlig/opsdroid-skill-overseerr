import logging
import asyncio
import time
import contextlib

import jinja2

from opsdroid.skill import Skill
from opsdroid.events import Message, Typing
from opsdroid.matchers import (match_regex,
                               match_catchall,
                               match_webhook)

from .config_schema import validate as validate_config
from .search import search_flow
from .requests import requests_flow
from .api import OverseerrAPI, OverseerrError, MediaStatus
from .plex import Plex
from .utils import parse_time, format_time_ago


CONTEXT_MAX_AGE = 180
CONTEXT_MAX_REPLIES = 3
HTTP_UNAUTHORIZED = 401


logger = logging.getLogger(__name__)


def configure_jinja():
    jinja = jinja2.Environment(
        loader=jinja2.PackageLoader(__name__),
        enable_async=True,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    jinja.globals.update(dict(
        MediaStatus=MediaStatus,
        parse_time=parse_time,
        format_time_ago=format_time_ago,
    ))
    return jinja


@contextlib.asynccontextmanager
async def error_responder(message):
    try:
        yield
    except OverseerrError as error:
        logger.error("server error: %s", error)
        if error.status == HTTP_UNAUTHORIZED:
            text = "Looks like I'm not authorized to do that on your " \
                   "behalf at the moment. Please use /login first " \
                   "(in a private chat with me)."
        else:
            text = f"Sorry, there was an error: {error.reason}"
        await message.respond(Message(text))
    except asyncio.CancelledError:
        raise
    except:
        logging.exception("something went wrong")
        text = "Something went wrong, sorry"
        await message.respond(Message(text))


class OverseerrSkill(Skill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        config = validate_config(self.config)
        self.bot_name = config["bot-name"]
        self.bot_url = config["bot-url"].rstrip("/")
        self.notify_room = config.get("notify-room")
        self.jinja = configure_jinja()
        self.plex = Plex(self.bot_name, self.bot_url,
                         self.opsdroid.web_server.web_app,
                         self.opsdroid.memory, self.jinja)

        self.rooms = {}
        for name, room in config["rooms"].items():
            self.configure_room(name, room)

    def configure_room(self, name, config):
        if isinstance(config, str):
            url = config
            api_key = None
            more_rooms = []
        else:
            url = config["url"]
            api_key = config.get("api-key")
            more_rooms = config["more-rooms"]

        api = OverseerrAPI(url, api_key)
        self.rooms[name] = RoomContext(name, self.jinja, api)

        for name in more_rooms:
            self.rooms[name] = RoomContext(name, self.jinja, api)

    def get_user_context(self, event):
        room = self.rooms.get(event.target)
        if room:
            return room.get_user_context(event.user_id)

    ### Decorators

    def with_error_responder(func):
        async def decorated(self, message):
            async with error_responder(message):
                await func(self, message)
        return decorated

    def with_user_context(func):
        async def decorated(self, message):
            context = self.get_user_context(message)
            if context:
                await func(self, message, context)
            else:
                logger.debug("message from unauthorized user %s",
                             message.user_id)
        return decorated

    def with_api_session(func):
        async def decorated(self, message, context):
            user_id = message.user_id
            session = context.new_session()
            auth_token = await self.plex.get_auth_token(user_id)
            if auth_token:
                try:
                    await session.login_plex(auth_token)
                except OverseerrError:
                    pass
            await func(self, message, context)
        return decorated

    def flow_starter(func):
        async def decorated(self, message, context):
            context.start_flow(message, func(self, message, context))
        return decorated

    ### Message handlers

    @match_regex(r"/h(elp)?$",
                 case_sensitive=False)
    @with_error_responder
    @with_user_context
    async def help(self, message, context):
        # context is unused but limits who can send the command
        await message.respond(Typing(True))
        tmpl = self.jinja.get_template("help.jinja")
        text = await tmpl.render_async({}, bot_name=self.bot_name)
        await message.respond(Message(text))

    @match_regex(r"/login$",
                 case_sensitive=False)
    @with_user_context
    async def plex_login(self, message, context):
        # context is unused but limits who can send the command
        user_id = message.user_id
        auth_url = self.plex.get_login_url(user_id)
        tmpl = self.jinja.get_template("login.jinja")
        text = await tmpl.render_async({}, auth_url=auth_url)
        await self.opsdroid.send(Message(text, target=user_id))

    @match_regex(r"/logout$",
                 case_sensitive=False)
    @with_error_responder
    @with_user_context
    async def plex_logout(self, message, context):
        # context is unused but limits who can send the command
        user_id = message.user_id
        if await self.plex.get_auth_token(user_id):
            await self.plex.delete_auth_token(user_id)
            text = "You have been logged out"
        else:
            text = "You haven't logged in yet"
        await self.opsdroid.send(Message(text, target=user_id))

    @match_regex(r"/s(earch)?(?P<term>\s.*)?$",
                 case_sensitive=False)
    @with_error_responder
    @with_user_context
    @with_api_session
    @flow_starter
    def search(self, message, context):
        return search_flow(message, context)

    @match_regex(r"/r(eq(uests)?)?(?P<kind>\s[^\s]*)?(?P<take>\s.*)?$",
                 case_sensitive=False)
    @with_error_responder
    @with_user_context
    @with_api_session
    @flow_starter
    def requests(self, message, context):
        return requests_flow(message, context)

    @match_regex(r"/abort$",
                 case_sensitive=False)
    @with_error_responder
    @with_user_context
    async def abort(self, message, context):
        if context.in_flow():
            text = "OK, aborting"
            await message.respond(Message(text))
            context.cancel()

    @match_catchall(messages_only=True)
    @with_error_responder
    @with_user_context
    async def catchall(self, message, context):
        if context.in_flow():
            context.put(message)

    ### Webhooks

    @match_webhook("notification")
    async def notification(self, request):
        room = self.notify_room
        if not room:
            logger.info("received a notification but no "
                        "notify-room is configured")
            return

        try:
            api = self.rooms[room].api
        except KeyError:
            api = None

        await self.opsdroid.send(Typing(True, target=room))
        data = await request.json()
        tmpl = self.jinja.get_template("notify.jinja")
        text = await tmpl.render_async(data, api=api)
        await self.opsdroid.send(Message(text, target=room))


class RoomContext:
    def __init__(self, name, jinja, api):
        self.name = name
        self.jinja = jinja
        self.api = api
        self.user_context = {}

    def get_user_context(self, user_id):
        self.forget_old_user_contexts()
        try:
            return self.user_context[user_id]
        except KeyError:
            context = UserContext(self, user_id)
            self.user_context[user_id] = context
            return context

    def forget_old_user_contexts(self):
        for user_id, context in list(self.user_context.items()):
            if context.get_age() > CONTEXT_MAX_AGE:
                self.user_context.pop(user_id).cancel()


class UserContext:
    def __init__(self, room_context, user_id):
        self.user_id = user_id
        self.jinja = room_context.jinja
        self.api = room_context.api
        self.session = None
        self.mtime = 0
        self.task = None
        self.queue = None
        self.last_message = None

    def touch(self):
        self.mtime = time.time()

    def get_age(self):
        return time.time() - self.mtime

    def new_session(self):
        self.session = self.api.new_session()
        return self.session

    def start_flow(self, message, coro):
        self.cancel()
        self.queue = asyncio.Queue()
        async def flow():
            async with error_responder(message):
                await coro
        self.task = asyncio.create_task(flow())
        self.touch()

    def cancel(self):
        if self.task:
            self.task.cancel()
            self.task = None
            self.queue = None

    def in_flow(self):
        return not (self.task is None or self.task.done())

    def get(self):
        return self.queue.get()

    def put(self, message):
        self.queue.put_nowait(message)

    async def get_and_parse(self, parser, away=None):
        # Try to get a response from the user and parse it using
        # the parser.
        for i in range(CONTEXT_MAX_REPLIES):
            message = await self.get()
            result = parser(message)
            if result is not None:
                self.touch()
                return result
        # Got 3 messages that didn't parse into sensible responses,
        # assume the person has moved on.
        #text = "You seem to have moved on, talk to you later"
        #await message.respond(Message(text))
        return away
