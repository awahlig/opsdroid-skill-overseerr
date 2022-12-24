import urllib.parse
from enum import IntEnum

import aiohttp


class MediaStatus(IntEnum):
    UNKNOWN = 1
    PENDING = 2
    PROCESSING = 3
    PARTIALLY_AVAILABLE = 4
    AVAILABLE = 5


class OverseerrError(Exception):
    def __init__(self, status, reason, message, errors):
        super().__init__(message or reason)
        self.status = status
        self.reason = reason
        self.message = message
        self.errors = errors

    def __str__(self):
        return f"OverseerrError({self.status!r}, {self.reason!r}, " \
            f"{self.message!r}, {self.errors!r})"


async def raise_for_status(resp):
    if resp.status < 400:
        return
    try:
        error = await resp.json()
    except ValueError:
        error = {}
    raise OverseerrError(resp.status, resp.reason,
                         error.get("message", ""),
                         error.get("errors", []))


class OverseerrAPI:
    def __init__(self, url, api_key=None):
        self.parsed_url = urllib.parse.urlparse(url)
        self.headers = {}
        if api_key:
            self.headers["X-Api-Key"] = api_key

    def make_abs_url(self, path, query=None, qs=""):
        if query:
            qs = "&".join("{}={}".format(k, urllib.parse.quote(str(v)))
                        for k, v in query.items() if v is not None)
        return self.parsed_url._replace(path=path, query=qs).geturl()

    def make_url(self, path, query=None, qs=""):
        return self.make_abs_url("/api/v1" + path, query, qs)

    def new_session(self):
        return OverseerrSession(self)


class OverseerrSession:
    def __init__(self, api):
        self.api = api
        self.session = aiohttp.ClientSession(headers=api.headers)

    async def get(self, path, query=None, qs=""):
        url = self.api.make_url(path, query, qs)
        async with self.session.get(url) as resp:
            await raise_for_status(resp)
            return await resp.json()

    async def post(self, path, data=None, query=None, qs=""):
        url = self.api.make_url(path, query, qs)
        async with self.session.post(url, json=data) as resp:
            await raise_for_status(resp)
            return await resp.json()

    async def delete(self, path, query=None, qs=""):
        url = self.api.make_url(path, query, qs)
        async with self.session.delete(url) as resp:
            await raise_for_status(resp)
            return await resp.read()

    ### Login

    async def login_plex(self, auth_token):
        data = {"authToken": auth_token}
        return await self.post("/auth/plex", data)

    async def login_local(self, username, password):
        data = {"username": username,
                "password": password}
        return await self.post("/auth/local", data)

    async def logout(self):
        return await self.post("/auth/logout")

    ### Search

    async def search(self, term, page=None, language=None):
        query = dict(query=term, page=page, language=language)
        return await self.get("/search", query)

    ### Requests

    async def list_requests(self, take=None, skip=None, kind=None,
                            order=None, requested_by=None):
        query = dict(take=take, skip=skip, filter=kind,
                     sort=order, requestedBy=requested_by)
        return await self.get("/request", query)

    async def get_request(self, request_id):
        return await self.get(f"/request/{request_id}")

    async def update_request_status(self, request_id, status):
        return await self.post(f"/request/{request_id}/{status}")

    async def delete_request(self, request_id):
        return await self.delete(f"/request/{request_id}")

    async def request(self, media_type, media_id,
                      server_id=None, profile_id=None, root_folder=None):
        data = {"mediaType": media_type,
                "mediaId": media_id}
        if server_id is not None:
            data["serverId"] = server_id
        if profile_id is not None:
            data["profileId"] = profile_id
        if root_folder is not None:
            data["rootFolder"] = root_folder
        return await self.post("/request", data)

    ### Media

    async def get_movie(self, movie_id, language=None):
        query = dict(language=language)
        return await self.get(f"/movie/{movie_id}", query)
        
    async def get_tv(self, tv_id, language=None):
        query = dict(language=language)
        return await self.get(f"/tv/{tv_id}", query)

    async def get_info(self, media):
        if media["mediaType"] == "movie":
            return await self.get_movie(media["tmdbId"])
        elif media["mediaType"] == "tv":
            return await self.get_tv(media["tmdbId"])
        return {}

    async def get_radarr_info(self, server_id=0):
        return await self.get(f"/service/radarr/{server_id}")
