import datetime


def parse_time(timestr):
    timestr = timestr.replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(timestr)


def format_time_ago(dt):
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - dt
    if delta.days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            mins = delta.seconds // 60
            if mins == 0:
                if delta.seconds == 0:
                    return "now"
                if delta.seconds == 1:
                    return "1 second ago"
                return "{} seconds ago".format(delta.seconds)
            if mins == 1:
                return "1 minute ago"
            return "{} minutes ago".format(mins)
        if hours == 1:
            return "1 hour ago"
        return "{} hours ago".format(hours)
    if delta.days == 1:
        return "1 day ago"
    return "{} days ago".format(delta.days)


def index_parser(array, default=None):
    async def parser(message):
        try:
            index = int(message.text) - 1
            if index < 0:
                raise IndexError
            return array[index]

        except (ValueError, IndexError):
            return default

    return parser
