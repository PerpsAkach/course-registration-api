from app import create_app
from app.waitlist import init_waitlist

app = create_app()
init_waitlist(app)
