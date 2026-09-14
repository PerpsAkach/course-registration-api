from app import create_app
from app.auth import init_auth
from app.waitlist import init_waitlist

app = create_app()
init_auth(app)
init_waitlist(app)
