import discord


class AutoTSSError(Exception):
    pass


class DeviceError(AutoTSSError):
    pass


class InvalidNameError(DeviceError):
    pass


class InvalidIdentifierError(DeviceError):
    pass


class InvalidECIDError(DeviceError):
    pass


class InvalidBoardConfigError(DeviceError):
    pass


class InvalidGeneratorError(DeviceError):
    pass


class InvalidApNonceError(DeviceError):
    pass


class StopCommand(AutoTSSError):
    pass


class SavingSHSHError(AutoTSSError):
    pass


class NotFound(AutoTSSError):
    pass


class NoDevicesFound(NotFound):
    def __init__(self, user: discord.User) -> None:
        super().__init__()
        self.user = user


class NoSHSHFound(NotFound):
    def __init__(self, user: discord.User) -> None:
        super().__init__()
        self.user = user


class TooManyDevices(AutoTSSError):
    def __init__(self, max_devices: int) -> None:
        super().__init__()
        self.max_devices = max_devices


class ViewTimeoutException(AutoTSSError):
    def __init__(self, timeout: int) -> None:
        super().__init__()
        self.timeout = timeout


class NotWhitelisted(AutoTSSError):
    def __init__(self, channel: discord.TextChannel, *args) -> None:
        super().__init__(*args)
        self.channel = channel
