# opsdroid-skill-overseerr
Opsdroid skill for https://overseerr.dev

## configuration

```yml
skills:
  overseerr:
    # URL of this repository for Opsdroid to automatically download
    # the skill from.
    repo: https://github.com/awahlig/opsdroid-skill-overseerr.git
    branch: main

    # What's this bot called? Defaults to "opsdroid".
    bot-name: opsdroid

    # The external URL of the Opsdroid web server.
    # Used for Plex auth callbacks and notifications.
    bot-url: https://my-opsdroid.com

    # List of Overseerr servers.
    servers:
      # The URL of the server (without /api).
      - url: https://my-overseerr.app

        # API key of the server. Optional.
        api-key: "..."

        # List of Opsdroid rooms that can access this server.
        rooms:
          - my-overseerr-room

        # List of rooms that receive webhook notifications. Optional.
        # <bot-url>/skill/overseerr/notification
        notify-rooms:
          - my-overseerr-room
```
