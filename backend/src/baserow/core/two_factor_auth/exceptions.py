class TwoFactorAuthTypeDoesNotExist(Exception):
    ...


class VerificationFailed(Exception):
    ...


class WrongPassword(Exception):
    ...


class TwoFactorAuthAlreadyConfigured(Exception):
    ...


class TwoFactorAuthNotConfigured(Exception):
    ...


class TwoFactorAuthCannotBeConfigured(Exception):
    ...
