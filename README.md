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

    # Name of the bot.
    bot-name: opsdroid

    # URL of the Opsdroid web server, used to serve the Plex login.
    bot-url: https://my-opsdroid.com

    # Rooms with access to Overseerr commands.
    rooms:
      # Room ID
      my-overseerr-room:
        # URL of the Overseerr API.
        url: https://my-overseerr.com

        # Overseerr API key.
        api-key: "..."

        # Marks the room as a target for webhook notifications.
        # <bot-url>/skill/overseerr/notification
        notify: false
```
