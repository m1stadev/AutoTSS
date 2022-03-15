from bot import DB_PATH
from hashlib import sha1, sha384
from .errors import *
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
                raise DeviceError(
                    'Device identifier must be set to fetch a board config.'
                )

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
            raise InvalidNameError("A device's name cannot be over 20 characters long.")

        async with aiosqlite.connect(DB_PATH) as db, db.execute(
            'SELECT devices from autotss WHERE user = ?', (user,)
        ) as cursor:  # Make sure the user doesn't have any other devices with the same name added
            try:
                devices = ujson.loads((await cursor.fetchone())[0])
            except:
                return name

        if any(x['name'] == name.casefold() for x in devices):
            raise InvalidNameError("The same name cannot be used for multiple devices.")

        return name

    async def verify_identifier(self, identifier: str) -> str:
        devices = await api.get_all_devices()

        if identifier.casefold() not in [
            device['identifier'].casefold() for device in devices
        ]:
            raise InvalidIdentifierError()

        return identifier

    async def verify_ecid(self, ecid: str) -> str:
        try:
            int(ecid, 16)  # Make sure the ECID provided is hexadecimal, not decimal
        except (ValueError, TypeError):
            raise InvalidECIDError()

        ecid = hex(int(ecid, 16)).removeprefix('0x')
        if ecid == 'abcdef0123456':  # This ECID is provided as an example in the modal
            raise InvalidECIDError()

        if (
            not 11 <= len(ecid) <= 13
        ):  # All hex ECIDs without zero-padding are between 11-13 characters
            raise InvalidECIDError()

        return ecid

    async def verify_boardconfig(self, identifier: str, boardconfig: str) -> str:
        if boardconfig[-2:] != 'ap':
            raise InvalidBoardConfigError()

        device = await api.get_device(identifier)
        if not any(
            b['boardconfig'].casefold() == boardconfig.casefold()
            for b in device['boards']
        ):  # If no boardconfigs for the given device identifier match the boardconfig, then return False
            raise InvalidBoardConfigError()

        return boardconfig

    def verify_generator(self, generator: str) -> str:
        if not generator.startswith('0x'):  # Generator must start wth '0x'
            raise InvalidGeneratorError()

        if (
            len(generator) != 18
        ):  # Generator must be 18 characters long, including '0x' prefix
            raise InvalidGeneratorError()

        try:
            int(generator, 16)  # Generator must be hexadecimal
        except:
            raise InvalidGeneratorError()

        return generator.lower()

    def verify_apnonce(self, cpid: int, nonce: str) -> str:
        try:
            int(nonce, 16)
        except ValueError or TypeError:
            raise InvalidApNonceError()

        if 0x8010 <= cpid < 0x8900:  # A10+ device ApNonces are 64 characters long
            apnonce_len = 64
        else:  # A9 and below device ApNonces are 40 characters
            apnonce_len = 40

        if len(nonce) != apnonce_len:
            raise InvalidApNonceError()

        return nonce

    def _verify_apnonce_pair(self) -> bool:
        gen = bytes.fromhex(self.generator.removeprefix('0x'))
        if len(self.apnonce) == 64:
            gen_hash = sha384(gen).hexdigest()[:-32]
        elif len(self.apnonce) == 40:
            gen_hash = sha1(gen).hexdigest()

        return gen_hash == self.apnonce

    async def verify_apnonce_pair(self) -> bool:
        return await asyncio.to_thread(self._verify_apnonce_pair)

    @property
    def censored_ecid(self) -> str:
        if getattr(self, 'ecid', None) is None:
            raise NotFound('No ECID for this device is set.')

        return ('*' * len(self.ecid))[:-4] + self.ecid[-4:]

    async def get_boardconfig(self) -> str:
        if getattr(self, 'identifier', None) is None:
            raise NotFound('No identifier for this device is set.')

        device = await api.get_device_info(self.identifier)

        valid_boards = [
            board['boardconfig']
            for board in device['boards']
            if board['boardconfig']
            .lower()
            .endswith('ap')  # Exclude development boards that may pop up
        ]

        if len(valid_boards) != 1:
            raise NotFound(
                'Multiple board configs for this device were found, one must be manually specified.'
            )

        return valid_boards[0].lower()

    async def get_cpid(self) -> str:
        for attr in ('boardconfig', 'identifier'):
            if getattr(self, attr, None) is None:
                raise NotFound(f'No {attr} for this device is set.')

        device = await api.get_device_info(self.identifier)

        try:
            return next(
                b['cpid']
                for b in device['boards']
                if b['boardconfig'].casefold() == self.boardconfig.casefold()
            )
        except StopIteration:
            raise DeviceError('Failed to retrieve the CPID for this device.')

    async def fetch_signed_firmwares(self) -> list:
        if getattr(self, 'identifier', None) is None:
            raise NotFound('No identifier for this device is set.')

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
