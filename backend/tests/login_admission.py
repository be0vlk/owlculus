"""Admission stub for tests whose scope is downstream authentication behavior."""


class AdmittedLogin:
    async def check(self, client_address: str, username: str) -> None:
        pass


def admitted_login():
    return AdmittedLogin()
