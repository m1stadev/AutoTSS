# AutoTSS
AutoTSS is a Discord bot that automatically saves [SHSH blobs](https://www.theiphonewiki.com/wiki/SHSH) for all of your iOS devices.

*Want a CLI automatic blob saver? Check out [AutoTSS-cli](https://github.com/marijuanARM/autotss-cli/)!*

## Disclaimer
- This should NOT be your main reliance for saving blobs. I am not at fault for any issues you may experience with AutoTSS.

## Features
- Automatic blob saving
- Custom apnonce support

## Setup
To locally host, follow these steps:

0. Create a [Discord Bot](https://discord.com/developers/applications/).
    - Under the bot menu, make sure to enable the 'Server Members Intent'.

1. Build and install [tsschecker](https://github.com/tihmstar/tsschecker/) and its dependencies.

2. Install the required libraries:
`pip3 install -r requirements.txt`

3. Create a file named `token.txt` and place your bot's token in it.

4. Run `bot.py`:
`python3 bot.py`

## Invite
AutoTSS can be invited into any Discord server using [this](https://discord.com/oauth2/authorize?client_id=804072225723383818&scope=bot&permissions=93184/) link.

## Support
For any questions/issues you have, join my [discord](https://discord.gg/fAngssA/).
