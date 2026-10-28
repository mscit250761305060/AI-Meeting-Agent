import sys
from app.services import meeting_state
from app.services import ws_manager
from app.database import database
from app.models import models

sys.modules['server.meeting_state'] = meeting_state
sys.modules['server.ws_manager'] = ws_manager
sys.modules['server.database'] = database
sys.modules['server.models'] = models
