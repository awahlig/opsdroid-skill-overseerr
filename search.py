import regex

from opsdroid.events import Message, Typing, Image

from .api import MediaStatus
from .utils import index_parser


async def search_flow(message, context):
    term = (message.regex.group("term") or "").strip()

    if not term:
        text = "What is the name of the movie or TV show you want to search for?"
        await message.respond(Message(text))
        message = await context.get()
        term = message.text.strip()
        context.touch()

    page = 0
    load_more = True
    all_results = []
    selected = None
    while True:
        if load_more:
            await message.respond(Typing(True))
            page += 1
            search = await context.session.search(term, page=page)
            # Filter out movies and tv shows.
            results = [r for r in search["results"]
                        if r["mediaType"] in {"movie", "tv"}]

            for index, result in enumerate(results, len(all_results) + 1):
                result["index"] = index

            total = search["totalResults"]
            skip = len(all_results)
            all_results.extend(results)
            load_more = False

            if len(all_results) != 1:
                tmpl = context.jinja.get_template("search/results.jinja")
                text = await tmpl.render_async({}, results=results, term=term,
                                            skip=skip, total=total)
                await message.respond(Message(text))

        if not all_results:
            return

        result_parser = index_parser(all_results)
        async def parser(message):
            text = message.text

            if regex.match(r"m(ore)?$", text, regex.I):
                return ("more", None)

            if selected:
                if regex.match(r"c(over)?$", text, regex.I):
                    return ("cover", selected)
                match = regex.match(r"r(eq(uest)?)?(?P<params>\s.*)?$", text, regex.I)
                if match:
                    return ("request", match)

            result = await result_parser(message)
            if result is not None:
                return ("result", result)

        if not selected and len(all_results) == 1:
            (command, argument) = ("result", all_results[0])
        else:
            (command, argument) = await context.get_and_parse(parser, ("away", None))

        if command == "result":
            selected = argument

            tmpl = context.jinja.get_template("search/details.jinja")
            text = await tmpl.render_async({}, result=selected, api=context.session.api)
            await message.respond(Message(text))

            text = "Would you like to see the «cover» or «request» the media?"
            await message.respond(Message(text))

        elif command == "cover":
            poster_path = argument.get("posterPath")
            if poster_path:
                name = poster_path.rsplit("/", 1)[-1]
                url = "https://image.tmdb.org/t/p/w600_and_h900_bestv2" + poster_path
                response = Image(name=name, url=url)
            else:
                response = Message("No cover image available")
            await message.respond(response)

        elif command == "request":
            params = (argument.group("params") or "").strip()
            context.start_flow(message, request_flow(message, context, selected, params))
            return

        elif command == "more":
            load_more = True

        elif command == "away":
            return


async def request_flow(message, context, selected, params):
    # Parse the params.
    params = params.split(' in ', 1)
    quality = params[0].strip().lower()
    if len(params) > 1:
        folder = params[1].strip().lower()
    else:
        folder = ""

    # Abort if media already requested.
    print(selected)
    status = selected.get("mediaInfo", {}) \
                     .get("status", MediaStatus.UNKNOWN)
    if status in (MediaStatus.PENDING,
                  MediaStatus.PROCESSING,
                  MediaStatus.AVAILABLE):
        text = "This media has already been requested, bye"
        await message.respond(Message(text))
        return

    # Get server info depending on media type.
    if selected["mediaType"] == "tv":
        server_info = await context.session.get_sonarr_server(0)
    else:
        server_info = await context.session.get_radarr_server(0)

    # If provided in params, match the quality with profile names.
    profile = None
    if quality:
        # Use the first matching profile.
        for item in server_info["profiles"]:
            if quality in item["name"].lower():
                profile = item
                break

    # No profile and server has only one - use it.
    if profile is None and len(server_info["profiles"]) == 1:
        profile = server_info["profiles"][0]

    # Still no profile? Ask which one to use.
    if profile is None:
        tmpl = context.jinja.get_template("request/profile.jinja")
        text = await tmpl.render_async(server_info)
        await message.respond(Message(text))
        parser = index_parser(server_info["profiles"])
        profile = await context.get_and_parse(parser)
        if profile is None:
            return

    # If provided in params, match the folder name with root folder paths.
    root_folder = None
    if folder:
        # Use the first matching folder.
        for item in server_info["rootFolders"]:
            if folder in item["path"].lower():
                root_folder = item
                break

    # No root folder and server has only one - use it.
    if root_folder is None and len(server_info["rootFolders"]) == 1:
        root_folder = server_info["rootFolders"][0]

    # Still no root folder path? Ask which one to use.
    if root_folder is None:
        tmpl = context.jinja.get_template("request/folder.jinja")
        text = await tmpl.render_async(server_info)
        await message.respond(Message(text))
        parser = index_parser(server_info["rootFolders"])
        root_folder = await context.get_and_parse(parser)
        if root_folder is None:
            return

    # Finally, request the media!
    await message.respond(Typing(True))
    data = await context.session.request(
        selected["mediaType"],
        selected["id"],
        server_id=0,
        profile_id=profile["id"],
        root_folder=root_folder["path"])

    tmpl = context.jinja.get_template("request/done.jinja")
    text = await tmpl.render_async(data, result=selected, profile=profile,
                                    root_folder=root_folder)
    await message.respond(Message(text))
