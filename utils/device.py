from bot import DB_PATH
from hashlib import sha1, sha384
from . import api

import aiosqlite
import asyncio
import discord
import ujson


class Device:
    def __init__(
        self,
        user: discord.User,
        name: str = None,
        identifier: str = None,
        ecid: str = None,
        boardconfig: str = None,
        generator: str = None,
        apnonce: str = None,
    ):
        loop = asyncio.get_event_loop()
        self.user = user

        if name is not None:
            self.name = self.verify_name(name, self.user.id)

        if identifier is not None:
            self.identifier = self.verify_identifier(identifier)

        if ecid is not None:
            self.ecid = self.verify_ecid(ecid)

        if boardconfig is not None:
            if getattr(self, 'identifier', None) is None:
                pass  # raise error

            self.boardconfig = self.verify_boardconfig(self.identifier, boardconfig)
        else:
            self.boardconfig = loop.run_until_complete(self.get_boardconfig())

        self.cpid = loop.run_until_complete(self.fetch_cpid())

        if generator is not None:
            self.generator = self.verify_generator(generator)

        if apnonce is not None:
            self.apnonce = self.verify_apnonce(self.identifier, apnonce)

    # Data verification functions
    async def verify_name(self, name: str, user: int) -> str:
        if len(name) > 20:  # Length check
            pass  # raise error

        async with aiosqlite.connect(DB_PATH) as db, db.execute(
            'SELECT devices from autotss WHERE user = ?', (user,)
        ) as cursor:  # Make sure the user doesn't have any other devices with the same name added
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except:
                return name

        if any(x['name'] == name.casefold() for x in devices):
            pass  # raise error

        return name

    async def verify_identifier(self, identifier: str) -> str:
        devices = await api.get_all_devices()

        if identifier.casefold() not in [
            device['identifier'].casefold() for device in devices
        ]:
            pass  # raise error

        return identifier

    async def verify_ecid(self, ecid: str) -> str:
        try:
            int(ecid, 16)  # Make sure the ECID provided is hexadecimal, not decimal
        except (ValueError, TypeError):
            pass  # raise error

        ecid = hex(int(ecid, 16)).removeprefix('0x')
        if ecid == 'abcdef0123456':  # This ECID is provided as an example in the modal
            pass  # raise error

        if (
            not 11 <= len(ecid) <= 13
        ):  # All hex ECIDs without zero-padding are between 11-13 characters
            pass  # raise error

        async with aiosqlite.connect(DB_PATH) as db, db.execute(
            'SELECT devices from autotss'
        ) as cursor:  # Make sure the ECID the user provided isn't already a device added to AutoTSS.
            try:
                devices = [device[0] for device in (await cursor.fetchall())]
            except TypeError:  # No devices in database
                return ecid

        if any(
            ecid in device_info for device_info in devices
        ):  # There's no need to convert the json string to a dict here
            pass  # raise error

        return ecid

    async def verify_boardconfig(self, identifier: str, boardconfig: str) -> str:
        if boardconfig[-2:] != 'ap':
            pass  # raise error

        device = await api.get_device(identifier)
        if not any(
            b['boardconfig'].casefold() == boardconfig.casefold()
            for b in device['boards']
        ):  # If no boardconfigs for the given device identifier match the boardconfig, then return False
            pass  # raise error

        return boardconfig

    def verify_generator(self, generator: str) -> str:
        if not generator.startswith('0x'):  # Generator must start wth '0x'
            pass  # raise error

        if (
            len(generator) != 18
        ):  # Generator must be 18 characters long, including '0x' prefix
            pass  # raise error

        try:
            int(generator, 16)  # Generator must be hexadecimal
        except:
            pass  # raise error

        return generator.lower()

    def verify_apnonce(self, cpid: int, nonce: str) -> str:
        try:
            int(nonce, 16)
        except ValueError or TypeError:
            pass  # raise error

        if 0x8010 <= cpid < 0x8900:  # A10+ device ApNonces are 64 characters long
            apnonce_len = 64
        else:  # A9 and below device ApNonces are 40 characters
            apnonce_len = 40

        if len(nonce) != apnonce_len:
            pass  # raise error

        return nonce

    def verify_apnonce_pair(self, generator: str, apnonce: str) -> bool:
        gen = bytes.fromhex(generator.removeprefix('0x'))
        if len(apnonce) == 64:
            gen_hash = sha384(gen).hexdigest()[:-32]
        elif len(apnonce) == 40:
            gen_hash = sha1(gen).hexdigest()

        return gen_hash == apnonce

    @property
    def censored_ecid(self) -> str:
        if getattr(self, 'ecid', None) is None:
            pass  # raise error

        return ('*' * len(self.ecid))[:-4] + self.ecid[-4:]

    async def get_boardconfig(self) -> str:
        if getattr(self, 'identifier', None) is None:
            pass  # raise error

        device = await api.get_device_info(self.identifier)

        valid_boards = [
            board['boardconfig']
            for board in device['boards']
            if board['boardconfig']
            .lower()
            .endswith('ap')  # Exclude development boards that may pop up
        ]

        if len(valid_boards) != 1:
            pass  # raise error

        return valid_boards[0].lower()

    async def get_cpid(self) -> str:
        if any(
            getattr(self, attr, None) is None for attr in ('boardconfig', 'identifier')
        ):
            pass  # raise error

        device = await api.get_device_info(self.identifier)

        try:
            return next(
                b['cpid']
                for b in device['boards']
                if b['boardconfig'].casefold() == self.boardconfig.casefold()
            )
        except StopIteration:
            pass  # raise error

    async def fetch_signed_firmwares(self) -> list:
        if getattr(self, 'identifier', None) is None:
            pass  # raise error

        data = await api.get_device_firmwares(self.identifier)

        firmwares = list()
        for firm in data:
            if firm['signed'] == False:
                continue

            data.append(
                {
                    'version': firm['version'],
                    'buildid': firm['buildid'],
                    'url': firm['url'],
                    'signed': firm['signed'],
                }
            )

        return firmwares
