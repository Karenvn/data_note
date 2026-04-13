from requests.auth import AuthBase
from base64 import b64encode


class GritJiraAuth(AuthBase):
    def __init__(self, username, password):
        # setup any auth-related data here
        self.username = username
        self.password = password

    def __call__(self, r):
        # modify and return the request
        if self.username == 'token':
            r.headers['Authorization'] = f"Bearer {self.password}"
        else:
            if isinstance(self.username, str):
                self.username = self.username.encode('latin1')

            if isinstance(self.password, str):
                self.password = self.password.encode('latin1')

            r.headers['Authorization'] = 'Basic ' + (
                b64encode(b':'.join((self.username, self.password))).strip().decode('ascii')
            )

        return r
