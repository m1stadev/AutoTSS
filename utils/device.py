from bot import DB_PATH
from hashlib import sha1, sha384
from typing import Optional
from .errors import DeviceError
from . import api

import aiosqlite
import asyncio
import discord
import ujson


class Device:
    async def init(  # A little hacky but it works ¯\_(ツ)_/¯
        self,
        user: discord.User,
        name: str = None,
        identifier: str = None,
        ecid: str = None,
        boardconfig: str = None,
        generator: str = None,
        apnonce: str = None,
        saved_blobs: list = None,
    ):
        self.user = user
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
            'saved_blobs': list(),  # TODO: Handle saved blobs
        }

    async def remove(self) -> None:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT devices from autotss WHERE user = ?',
                (
                    self.user.id,
                ),  # TODO: Change so that it finds user via the ECID rather than checking with user ID
            ) as cursor:
                try:
                    devices = ujson.loads((await cursor.fetchone())[0])
                except TypeError:
                    pass  # raise error

            try:
                device = next(d for d in devices if d['ecid'] == self.ecid)
            except StopIteration:
                raise DeviceError('Device not found in db???')

            devices.remove(device)
            if len(devices) == 0:
                await db.execute('DELETE FROM autotss WHERE user = ?', (self.user.id,))
            else:
                await db.execute(
                    'UPDATE autotss SET devices = ? WHERE user = ?',
                    (ujson.dumps(devices), self.user.id),
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
            raise DeviceError('Invalid device identifier provided.')

        return identifier

    def verify_ecid(self, ecid: str) -> Optional[str]:
        if ecid is None:
            return

        try:
            int(ecid, 16)  # Make sure the ECID provided is hexadecimal, not decimal
        except (ValueError, TypeError):
            raise DeviceError('Invalid ECID provided.')

        ecid = hex(int(ecid, 16)).removeprefix('0x')
        if ecid == 'abcdef0123456':  # This ECID is provided as an example in the modal
            raise DeviceError('Invalid ECID provided.')

        if len(ecid) not in (
            11,
            13,
        ):  # All hex ECIDs without zero-padding are between 11-13 characters
            raise DeviceError('Invalid ECID provided.')

        return ecid

    async def verify_board(self, identifier: str, board: str) -> Optional[str]:
        if any(arg is None for arg in (identifier, board)):
            return

        if board[-2:] != 'ap':
            raise DeviceError('Invalid board config provided.')

        device = await api.get_device_info(identifier)
        if not any(
            b['boardconfig'].casefold() == board.casefold() for b in device['boards']
        ):  # If no boards for the given device identifier match the board, then return False
            raise DeviceError('Invalid board config provided.')

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

        return gen_hash == self.apnonce

    async def verify_apnonce_pair(self) -> Optional[bool]:
        if any(arg is None for arg in (self.apnonce, self.generator)):
            return

        return await asyncio.to_thread(self._verify_apnonce_pair)

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
