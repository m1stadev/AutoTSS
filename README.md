# AutoTSS

[![License](https://img.shields.io/github/license/m1stadev/AutoTSS)](https://github.com/m1stadev/AutoTSS/blob/master/LICENSE)
[![Stars](https://img.shields.io/github/stars/m1stadev/AutoTSS)](https://github.com/m1stadev/AutoTSS/stargazers)
[![LoC](https://img.shields.io/tokei/lines/github/m1stadev/AutoTSS)](https://github.com/m1stadev/AutoTSS)
[![AutoTSS Invite](https://img.shields.io/badge/Discord-Invite%20AutoTSS-%237289DA)](https://m1sta.xyz/autotss)

Automatically save [SHSH blobs](https://www.theiphonewiki.com/wiki/SHSH) for all of your iOS devices through Discord.

*Want an automatic CLI blob saver? Check out [AutoTSS-cli](https://github.com/m1stadev/autotss-cli)!*

### Comparison with similar tools

| Feature | [AutoTSS](https://github.com/m1stadev/AutoTSS) | [shsh.host](https://shsh.host) | [TSSSaver](https://tsssaver.1conan.com/v2/) | [blobsaver](https://github.com/airsquared/blobsaver) | [tsschecker](https://github.com/1Conan/tsschecker) | [shshd](https://github.com/Diatrus/shshdaemon) |
|-|-|-|-|-|-|-|
| A12+ support | ✅* | ✅* | ✅* | ✅ | ✅ | ✅ |
| Doesn't require a jailbreak | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Saves SHSH blobs automatically | ✅ | ❌ | ❌ | ✅** | ❌ | ✅ |
| Doesn't use local system resources | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Saves SHSH blobs for beta iOS versions | ✅ | ✅ | ❌ | ✅*** | ✅*** | ❌ |
| Automatically grabs generator-apnonce combo | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Detects "signing parties" | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

<sup>* Requires users to already have a generator-apnonce combination for their device, more information on that can be found [here](https://www.reddit.com/r/jailbreak/comments/m3744k/tutorial_shsh_generatorbootnonce_apnonce_nonce/).</sup><br>
<sup>** Requires users to leave blobsaver always running.</sup><br>
<sup>*** Requires users to manually specify a BuildManifest from a beta IPSW.</sup>

## Running
To locally host your own instance, [create a Discord bot](https://discord.com/developers) and follow these steps...

1. Build and install [`tsschecker`](https://github.com/1Conan/tsschecker) and its dependencies

    If running on Windows, download the latest `tsschecker` release from [here](https://github.com/1Conan/tsschecker/releases), rename the binary to `tsschecker.exe`, then place it in the AutoTSS directory.

2. Create a virtual env and install dependencies

        python3 -m venv --upgrade-deps env && source env/bin/activate
        pip3 install -Ur requirements.txt

3.  Set the `AUTOTSS_TOKEN` environment variable to the bot token you got from your Discord bot application

    This can be done by exporting `AUTOTSS_TOKEN` in should shell configuration file, then reloading your shell

4. Start your instance

        python3 bot.py

AutoTSS needs the members intent to be enabled. This can be done by going to the bot menu in your Discord bot application, and enabling the "Server Members Intent".

## Support

For any questions/issues you have, join my [Discord](https://m1sta.xyz/discord).
