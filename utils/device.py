from bot import DB_PATH, MAX_USER_DEVICES, OWNER_ID
from hashlib import sha1, sha384
from typing import Optional
from .errors import DeviceError, TooManyDevices
from . import api

import aiosqlite
import asyncio
import discord
import ujson


class Device:
    async def init(  # A little hacky but it works ¯\_(ツ)_/¯
        self,
        name: str = None,
        identifier: str = None,
        ecid: str = None,
        boardconfig: str = None,
        generator: str = None,
        apnonce: str = None,
        saved_blobs: list = None,
    ):
        self.blobs = saved_blobs

        self.name = self.verify_name(name)
        self.identifier = await self.verify_identifier(identifier)
        self.ecid = self.verify_ecid(ecid)

        if boardconfig is None:
            self.board = await self.get_board()
        else:
            if getattr(self, 'identifier', None) is None:
                raise DeviceError('No device identifier provided.')

            self.board = await self.verify_board(self.identifier, boardconfig)

        self.generator = self.verify_generator(generator)
        self.cpid = await self.get_cpid()
        self.apnonce = self.verify_apnonce(apnonce)

        return self

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'identifier': self.identifier,
            'ecid': self.ecid,
            'boardconfig': self.board,
            'generator': self.generator,
            'apnonce': self.apnonce,
            'saved_blobs': self.blobs,  # TODO: Build class for firmwares/blobs
        }

    async def add(self, user: discord.User, enabled: bool = True) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT user FROM autotss WHERE devices like ?',
                (f'%"{self.ecid}"%',),
            ) as cursor:
                if await cursor.fetchone() is not None:
                    raise DeviceError('Device already exists in database.')

            async with db.execute(
                'SELECT devices FROM autotss WHERE user = ?', (user.id,)
            ) as cursor:
                data = await cursor.fetchone()

            if data is None:
                await db.execute(
                    'INSERT INTO autotss(user, devices, enabled) VALUES(?,?,?)',
                    (user.id, ujson.dumps([self.to_dict()]), enabled),
                )

            else:
                try:
                    devices = ujson.loads(data[0])
                except TypeError:
                    devices = list()

                if any(self.name.casefold() == d['name'].casefold() for d in devices):
                    raise DeviceError(
                        'Multiple devices with the same name are not allowed.'
                    )

                devices.append(self.to_dict())

                if len(devices) > MAX_USER_DEVICES and user.id == OWNER_ID:
                    raise TooManyDevices()

                await db.execute(
                    'UPDATE autotss SET devices = ? WHERE user = ?',
                    (ujson.dumps(devices), user.id),
                )

            await db.commit()

    async def remove(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT user, devices FROM autotss WHERE devices like ?',
                (f'%"{self.ecid}"%',),
            ) as cursor:
                data = await cursor.fetchone()

            try:
                user, devices = [data[0], ujson.loads(data[1])]
            except TypeError:
                raise DeviceError('Device not found in database.')

            try:
                device = next(d for d in devices if d['ecid'] == self.ecid)
            except StopIteration:
                raise DeviceError(
                    'Device has disappeared from database???'
                )  # This shouldn't happen...

            devices.remove(device)

            if len(devices) == 0:
                await db.execute('DELETE FROM autotss WHERE user = ?', (user,))
            else:
                await db.execute(
                    'UPDATE autotss SET devices = ? WHERE user = ?',
                    (ujson.dumps(devices), user),
                )

            await db.commit()

        del self

    # Data verification functions
    def verify_name(self, name: str) -> Optional[str]:
        if name is None:
            return

        if len(name) > 20:  # Length check
            raise DeviceError("A device's name cannot be over 20 characters long.")

        return name

    async def verify_identifier(self, identifier: str) -> Optional[str]:
        if identifier is None:
            return

        devices = await api.get_all_devices()

        if identifier.casefold() not in [
            device['identifier'].casefold() for device in devices
        ]:
            raise DeviceError(
                'Invalid device identifier provided. This can be found with [AIDA64](https://apps.apple.com/app/apple-store/id979579523) under the `Device` section (as `Device String`).'
            )

        if not any(
            id in identifier.lower() for id in ('iphone', 'ipod', 'ipad', 'appletv')
        ):
            raise DeviceError('Unsupported device.')

        return identifier

    def verify_ecid(self, ecid: str) -> Optional[str]:
        if ecid is None:
            return

        try:
            int(ecid, 16)  # Make sure the ECID provided is hexadecimal, not decimal
        except (ValueError, TypeError):
            raise DeviceError(
                'Invalid ECID provided. This can be found using one of the methods listed [here](https://www.theiphonewiki.com/wiki/ECID), under **Getting the ECID**.'
            )

        ecid = hex(int(ecid, 16)).removeprefix('0x')
        if ecid == 'abcdef0123456':  # This ECID is provided as an example in the modal
            raise DeviceError(
                'Invalid ECID provided. This can be found using one of the methods listed [here](https://www.theiphonewiki.com/wiki/ECID), under **Getting the ECID**.'
            )

        if len(ecid) not in (
            10,
            11,
            13,
            14,
        ):  # All hex ECIDs without zero-padding are either 10, 11, 13, or 14 characters long
            raise DeviceError(
                'Invalid ECID provided. This can be found using one of the methods listed [here](https://www.theiphonewiki.com/wiki/ECID), under **Getting the ECID**.'
            )

        return ecid

    async def verify_board(self, identifier: str, board: str) -> Optional[str]:
        if any(arg is None for arg in (identifier, board)):
            return

        if board[-2:] != 'ap':
            raise DeviceError(
                "Invalid board config provided. This value ends in `ap`, and can be found using one of the following:\n\n• [AIDA64](https://apps.apple.com/app/apple-store/id979579523) (under the `Device` section, as `Device Id`).\n• [System Info](https://arx8x.github.io/depictions/systeminfo.html) (under `System->General->About->Platform`).\n• Running `gssc | grep HWModelStr` in a terminal on your iOS device."
            )

        device = await api.get_device_info(identifier)
        if not any(
            b['boardconfig'].casefold() == board.casefold() for b in device['boards']
        ):  # If no boards for the given device identifier match the board, then return False
            raise DeviceError(
                "Invalid board config provided. This value ends in `ap`, and can be found using one of the following:\n\n• [AIDA64](https://apps.apple.com/app/apple-store/id979579523) (under the `Device` section, as `Device Id`).\n• [System Info](https://arx8x.github.io/depictions/systeminfo.html) (under `System->General->About->Platform`).\n• Running `gssc | grep HWModelStr` in a terminal on your iOS device."
            )

        return board

    def verify_generator(self, generator: str) -> Optional[str]:
        if generator is None:
            return

        if not generator.startswith('0x'):  # Generator must start wth '0x'
            raise DeviceError('Invalid nonce generator provided.')

        if (
            len(generator) != 18
        ):  # Generator must be 18 characters long, including '0x' prefix
            raise DeviceError('Invalid nonce generator provided.')

        try:
            int(generator, 16)  # Generator must be hexadecimal
        except:
            raise DeviceError('Invalid nonce generator provided.')

        return generator.lower()

    def verify_apnonce(self, nonce: str) -> Optional[str]:
        if any(arg is None for arg in (self.cpid, nonce)):
            return

        try:
            int(nonce, 16)
        except ValueError or TypeError:
            raise DeviceError('Invalid ApNonce provided.')

        if 0x8010 <= self.cpid < 0x8900:  # A10+ device ApNonces are 64 characters long
            apnonce_len = 64
        else:  # A9 and below device ApNonces are 40 characters
            apnonce_len = 40

        if len(nonce) != apnonce_len:
            raise DeviceError('Invalid ApNonce provided.')

        return nonce

    def _verify_apnonce_pair(self) -> bool:
        gen = bytes.fromhex(self.generator.removeprefix('0x'))
        if len(self.apnonce) == 64:
            gen_hash = sha384(gen).hexdigest()[:-32]
        elif len(self.apnonce) == 40:
            gen_hash = sha1(gen).hexdigest()

        if gen_hash != self.apnonce:
            raise DeviceError('Invalid generator-ApNonce pair provided.')

    async def verify_apnonce_pair(self) -> Optional[bool]:
        if any(arg is None for arg in (self.apnonce, self.generator)):
            return

        await asyncio.to_thread(self._verify_apnonce_pair)

    @property
    def censored_ecid(self) -> str:
        if getattr(self, 'ecid', None) is None:
            raise DeviceError('No ECID for this device is set.')

        return ('*' * len(self.ecid))[:-4] + self.ecid[-4:]

    async def get_board(self) -> str:
        if getattr(self, 'identifier', None) is None:
            raise DeviceError('No identifier for this device is set.')

        device = await api.get_device_info(self.identifier)

        valid_boards = [
            board['boardconfig']
            for board in device['boards']
            if board['boardconfig']
            .lower()
            .endswith('ap')  # Exclude development boards that may pop up
        ]

        if len(valid_boards) != 1:
            raise DeviceError(
                'Multiple board configs for this device were found, one must be manually specified.'
            )

        return valid_boards[0].lower()

    async def get_cpid(self) -> str:
        for attr in ('board', 'identifier'):
            if getattr(self, attr, None) is None:
                return

        device = await api.get_device_info(self.identifier)

        try:
            return next(
                b['cpid']
                for b in device['boards']
                if b['boardconfig'].casefold() == self.board.casefold()
            )
        except StopIteration:
            raise DeviceError('Failed to retrieve the CPID for this device.')

    async def fetch_signed_firmwares(self) -> list:
        if getattr(self, 'identifier', None) is None:
            raise DeviceError('No identifier for this device is set.')

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
