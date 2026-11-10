
DEMO_ADMIN_USERNAME = "admin123"
DEMO_ADMIN_PASSWORD = "password123"


class DemoAuthenticator:


    def __init__(self, username=DEMO_ADMIN_USERNAME, password=DEMO_ADMIN_PASSWORD):
        

        self.username = username
        self.password = password

    def authenticate_admin(self, username, password):

        return username == self.username and password == self.password