import discord


class AutoTSSError(Exception):
    pass


class APIError(AutoTSSError):
    def __init__(self, status: int, *args) -> None:
        super().__init__(*args)
        self.status = status


class DeviceError(AutoTSSError):
    pass


class StopCommand(AutoTSSError):
    pass


class SavingSHSHError(AutoTSSError):
    pass


class NoDevicesFound(AutoTSSError):
    def __init__(self, user: discord.User, *args) -> None:
        super().__init__(*args)
        self.user = user


class NoSHSHFound(AutoTSSError):
    def __init__(self, user: discord.User, *args) -> None:
        super().__init__(*args)
        self.user = user


class TooManyDevices(AutoTSSError):
    def __init__(self, max_devices: int, *args) -> None:
        super().__init__(*args)
        self.max_devices = max_devices


class ViewTimeoutException(AutoTSSError):
    def __init__(self, timeout: int, *args) -> None:
        super().__init__(*args)
        self.timeout = timeout


class NotWhitelisted(AutoTSSError):
    def __init__(self, channel: discord.TextChannel, *args) -> None:
        super().__init__(*args)
        self.channel = channel
