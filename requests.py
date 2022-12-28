import regex

from opsdroid.events import Message, Typing, Image

from .api import MediaStatus
from .utils import index_parser


async def requests_flow(message, context):
    kind = (message.regex.group("kind") or "all").strip().lower()
    valid = "all approved available pending processing unavailable failed".split()
    match = [name for name in valid if name.startswith(kind)]
    if len(match) == 1:
        kind = match[0]
    else:
        text = f"Sorry, '{kind}' does not uniquely identify a valid request type. " \
                f"Request types are:\n{', '.join(valid)}"
        await message.respond(Message(text))
        return

    try:
        take = int(message.regex.group("take") or 10)
    except ValueError:
        text = "Sorry, the count must be a number"
        await message.respond(Message(text))
        return
    if take < 1:
        take = 1

    load_more = True
    all_results = []
    selected = None
    while True:
        if load_more:
            await message.respond(Typing(True))
            skip = len(all_results)
            response = await context.session.list_requests(take=take, skip=skip, kind=kind)
            total = response["pageInfo"]["results"]
            results = response["results"]

            for index, result in enumerate(results, len(all_results) + 1):
                result["index"] = index
                result["info"] = await context.session.get_info(result["media"])

            all_results.extend(results)
            load_more = False

            if len(all_results) != 1:
                tmpl = context.jinja.get_template("requests/results.jinja")
                text = await tmpl.render_async({}, results=results, skip=skip,
                                                kind=kind, total=total)
                await message.respond(Message(text))

        if not all_results:
            return

        result_parser = index_parser(all_results)
        def parser(message):
            text = message.text

            if regex.match(r"m(ore)?$", text, regex.I):
                return ("more", None)

            if selected:
                if selected["media"]["status"] == MediaStatus.PENDING:
                    if regex.match(r"a(pprove)?$", text, regex.I):
                        return ("approve", selected)
                    if regex.match(r"d(ecline)?$", text, regex.I):
                        return ("decline", selected)

                if regex.match(r"c(over)?$", text, regex.I):
                    return ("cover", selected)
                if regex.match(r"r(etry)?$", text, regex.I):
                    return ("retry", selected)
                if regex.match(r"del(ete)?$", text, regex.I):
                    return ("delete", selected)

            result = result_parser(message)
            if result is not None:
                return ("result", result)

        if not selected and len(all_results) == 1:
            (command, argument) = ("result", all_results[0])
        else:
            (command, argument) = await context.get_and_parse(parser, ("away", None))

        if command == "result":
            selected = argument

            # Refresh in case it's downloading and there's new data.
            update = await context.session.get_request(selected["id"])
            selected.update(update)

            tmpl = context.jinja.get_template("requests/details.jinja")
            text = await tmpl.render_async({}, result=selected, api=context.session.api)
            await message.respond(Message(text))

            actions = ["see the «cover»"]
            status = selected["media"]["status"]
            if status == MediaStatus.PENDING:
                actions.extend(["«approve»", "«decline»"])
            actions.append("«retry»")
            text = f"Would you like to {', '.join(actions)} or «delete» this request?"
            await message.respond(Message(text))

        elif command == "cover":
            poster_path = argument["info"].get("posterPath")
            if poster_path:
                name = poster_path.rsplit("/", 1)[-1]
                url = "https://image.tmdb.org/t/p/w600_and_h900_bestv2" + poster_path
                response = Image(name=name, url=url)
            else:
                response = Message("No cover image available")
            await message.respond(response)

        elif command in {"approve", "decline", "retry"}:
            await message.respond(Typing(True))
            await context.session.update_request_status(argument["id"], command)
            if command == "approve":
                text = "OK, request has been approved"
            elif command == "decline":
                text = "OK, request has been declined"
            else:
                text = "OK, retry has been issued"
            await message.respond(Message(text))

        elif command == "delete":
            await message.respond(Typing(True))
            await context.session.delete_request(argument["id"])
            text = "OK, request deleted"
            await message.respond(Message(text))

        elif command == "more":
            load_more = True

        elif command == "away":
            return
