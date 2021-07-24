# AutoTSS
[![License](https://img.shields.io/github/license/m1stadev/AutoTSS)](https://github.com/m1stadev/AutoTSS)
[![Stars](https://img.shields.io/github/stars/m1stadev/AutoTSS)]((https://github.com/m1stadev/AutoTSS))
[![LoC](https://img.shields.io/tokei/lines/github/m1stadev/AutoTSS)](https://github.com/m1stadev/AutoTSS)

AutoTSS is a Discord bot that automatically saves [SHSH blobs](https://www.theiphonewiki.com/wiki/SHSH) for all of your iOS devices.

*Want a CLI automatic blob saver? Check out [AutoTSS-cli](https://github.com/m1stadev/autotss-cli)!*

## Disclaimer
- I am not at fault for any issues you may experience with AutoTSS.

## Feature comparison with similar tools
| Feature | [AutoTSS](https://github.com/m1stadev/AutoTSS) | [shsh.host](https://shsh.host) | [TSSSaver](https://tsssaver.1conan.com/v2/) | [blobsaver](https://github.com/airsquared/blobsaver) | [tsschecker](https://github.com/1Conan/tsschecker) | [shshd](https://github.com/diatrus/shshdaemon) |
|-|-|-|-|-|-|-|
| A12+ support | ✅* | ✅* | ✅* | ✅ | ✅ | ✅ |
| Doesn't require a jailbreak | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Saves SHSH blobs automatically | ✅ | ❌ | ❌ | ✅** | ❌ | ✅ |
| Doesn't use local system resources | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Saves SHSH blobs for beta iOS versions | ✅ | ✅ | ❌ | ✅*** | ✅*** | ❌ |
| Detects signing parties | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

<sup>* Requires users to already have a generator-apnonce combination for their device, more information on that can be found [here](https://www.reddit.com/r/jailbreak/comments/m3744k/tutorial_shsh_generatorbootnonce_apnonce_nonce/).</sup>

<sup>** Requires users to leave blobsaver always running.</sup>

<sup>*** Requires users to manually specify a BuildManifest from a beta IPSW.</sup>

## Setup
To locally host, follow these steps:

0. Create a [Discord Bot](https://discord.com/developers/applications).
    - Under the bot menu, make sure to enable the 'Server Members Intent'.

1. Build and install [tsschecker](https://github.com/1Conan/tsschecker) and its dependencies.

2. Install the required libraries:
`pip3 install -r requirements.txt`

3. Set the `AUTOTSS_TOKEN` environment variable to the bot token you got in Step 0.

4. Run `bot.py`:
`python3 bot.py`

## Invite
AutoTSS can be invited into any Discord server using [this](https://discord.com/oauth2/authorize?client_id=804072225723383818&scope=bot&permissions=93184) link.

## Support
For any questions/issues you have, join my [Discord](https://m1sta.xyz/discord).
