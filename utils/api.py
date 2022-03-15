from aiocache import cached

import aiohttp


RELEASE_API = 'https://api.ipsw.me/v4'
BETA_API = 'https://api.m1sta.xyz/betas'


@cached(ttl=600)
async def get_all_devices() -> list:
    async with aiohttp.ClientSession() as session, session.get(
        f'{RELEASE_API}/devices'
    ) as resp:
        if resp.status == 200:
            return await resp.json()
        else:
            return list()


async def get_device_info(identifier: str) -> dict:
    data = await get_all_devices()
    if len(data) == 0:
        pass  # raise error

    try:
        return next(
            d for d in data if d['identifier'].casefold() == identifier.casefold()
        )
    except StopIteration:
        pass  # raise error


async def fetch_device_firmwares(identifier: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{RELEASE_API}/device/{identifier}') as resp:
            if resp.status == 200:
                release_data = (await resp.json())['firmwares']
            else:
                release_data = list()

        async with session.get(f'{BETA_API}/{identifier}') as resp:
            if resp.status == 200:
                beta_data = [
                    firm for firm in await resp.json() if 'signed' in firm.keys()
                ]
            else:
                beta_data = list()

        for firm in list(
            beta_data
        ):  # Get rid of any beta firmwares that share buildids with releases
            if any(
                build in firm['buildid']
                for build in [f['buildid'] for f in release_data]
            ):
                beta_data.remove(firm)

        return sorted(
            release_data + beta_data, key=lambda x: x['buildid'], reverse=True
        )
