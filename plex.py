import platform
import urllib.parse

import aiohttp
from aiohttp import web


PATH_LOGIN = "/plex/login"
PATH_AUTH = "/plex/auth"
HTTP_NOT_FOUND = 404


class Plex:
    def __init__(self, product, base_url, web_app, memory, jinja):
        self.base_url = base_url
        self.memory = memory
        self.jinja = jinja
        self.product = product
        web_app.router.add_get(PATH_LOGIN, self.handle_login)
        web_app.router.add_get(PATH_AUTH, self.handle_auth)

    def get_login_url(self, user_id):
        params = dict(u=user_id)
        query = urllib.parse.urlencode(params)
        return f"{self.base_url}{PATH_LOGIN}?{query}"

    async def handle_login(self, request):
        user_id = request.query.get("u")
        if not user_id:
            raise web.HTTPBadRequest()

        params = dict(u=user_id)
        query = urllib.parse.urlencode(params)
        forward_url = f"{self.base_url}{PATH_AUTH}?{query}"

        headers = self.get_headers(user_id)
        tmpl = self.jinja.get_template("plex/login.html.jinja")
        body = await tmpl.render_async({}, headers=headers,
                                       forward_url=forward_url)
        return web.Response(body=body, content_type="text/html")

    async def handle_auth(self, request):
        user_id = request.query.get("u")
        pin_id = request.query.get("p")
        client_id = request.query.get("c")
        if not user_id or not pin_id or not client_id:
            raise web.HTTPBadRequest()

        try:
            pin = await self.get_pin(pin_id, client_id, user_id)
        except aiohttp.ClientResponseError as error:
            if error.status == HTTP_NOT_FOUND:
                raise web.HTTPNotFound(text="Request no longer valid")
            raise

        auth_token = pin["authToken"]
        if not auth_token:
            raise web.HTTPUnauthorized()
        await self.set_auth_token(user_id, auth_token)

        headers = self.get_headers(user_id)
        tmpl = self.jinja.get_template("plex/auth.html.jinja")
        body = await tmpl.render_async({}, headers=headers)
        return web.Response(body=body, content_type="text/html")

    async def get_auth_token(self, user_id):
        return await self.memory.get(auth_token_key(user_id))

    async def set_auth_token(self, user_id, auth_token):
        await self.memory.put(auth_token_key(user_id), auth_token)

    async def delete_auth_token(self, user_id):
        await self.memory.delete(auth_token_key(user_id))

    def get_headers(self, user_id):
        return {
            "Accept": "application/json",
            "X-Plex-Device-Name": "opsdroid-skill-overseerr",
            "X-Plex-Version": user_id,
            "X-Plex-Model": user_id,
            "X-Plex-Product": self.product,
            "X-Plex-Device": platform.system(),
            "X-Plex-Language": "en",
        }

    async def get_pin(self, pin_id, client_id, user_id):
        headers = self.get_headers(user_id)
        headers["X-Plex-Client-Identifier"] = client_id

        async with aiohttp.ClientSession(headers=headers,
                                        raise_for_status=True) as session:
            response = await session.get(f"https://plex.tv/api/v2/pins/{pin_id}")
            return await response.json()


def auth_token_key(user_id):
    return f"overseerr/{user_id}/plex-token"
