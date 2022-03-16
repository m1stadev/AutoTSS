<p align="center">
<img src="assets/autotss.png" alt="https://github.com/m1stadev/AutoTSS" width=256px> 
</p>

<h1 align="center">
AutoTSS
</h1>
<p align="center">
  <a href="https://github.com/m1stadev/AutoTSS/blob/master/LICENSE">
    <image src="https://img.shields.io/github/license/m1stadev/AutoTSS">
  </a>
  <a href="https://github.com/m1stadev/AutoTSS/stargazers">
    <image src="https://img.shields.io/github/stars/m1stadev/AutoTSS">
  </a>
  <a href="https://github.com/m1stadev/AutoTSS">
    <image src="https://img.shields.io/tokei/lines/github/m1stadev/AutoTSS">
  </a>
  <a href="https://m1sta.xyz/autotss">
    <image src="https://img.shields.io/badge/Discord-Invite%20AutoTSS-%237289DA">
  </a>
    <br>
</p>

<p align="center">
Automatically save <a href="https://www.theiphonewiki.com/wiki/SHSH">SHSH blobs</a> for all of your iOS devices through Discord.
</p>
<p align="center">
  <em>Want an automatic CLI blob saver? Check out <a href="https://github.com/m1stadev/autotss-cli">AutoTSS-cli</a>!</em>
</p>

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

<sup>* Requires users to already have a generator-apnonce combination for their device, more information on that can be found [here](https://gist.github.com/5464ea557c2b999cb9324639c777cd09#whats-nonce-entanglement).</sup><br>
<sup>** Requires users to leave blobsaver always running.</sup><br>
<sup>*** Requires users to manually specify a BuildManifest from a beta IPSW.</sup>

## Running
To locally host your own instance, [create a Discord bot](https://discord.com/developers) and follow these steps:

1. Build and install [`tsschecker`](https://github.com/1Conan/tsschecker) and its dependencies

    If running on Windows, you can download the latest `tsschecker` release from [here](https://github.com/1Conan/tsschecker/releases) and place it in the AutoTSS directory.

2. Create a virtual env and install dependencies

        python3 -m venv --upgrade-deps env && source env/bin/activate
        pip3 install -Ur requirements.txt

3.  Create a `.env` file and set the following environment variables:
  - `AUTOTSS_MAX_DEVICES` - Number of devices to allow users to add
  - `AUTOTSS_TOKEN` - AutoTSS token
  - `AUTOTSS_OWNER` - ID of the user that owns the bot
  - `AUTOTSS_TEST_GUILD` - (Optional) ID of guild to create commands in for testing
  - `AUTOTSS_WEBHOOK` - (Optional) URL to a Discord webhook for logging
  - Example `.env` file:

        AUTOTSS_MAX_DEVICES=10
        AUTOTSS_TOKEN=<TOKEN>
        AUTOTSS_OWNER=<OWNER ID>


4. Start AutoTSS

        python3 bot.py

AutoTSS needs the members intent to be enabled. This can be done by going to the bot menu in your Discord bot application, and enabling the "Server Members Intent".

## Support

For any questions/issues you have, join my [Discord](https://m1sta.xyz/discord).
