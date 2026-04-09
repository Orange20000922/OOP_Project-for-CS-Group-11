from app.services.auth_service import AuthService
from app.services.schedule_service import ScheduleService
from app.services.scnu_scraper import SCNUScraper
from app.storage.schedule_store import ScheduleStore
from app.storage.user_store import UserStore

user_store = UserStore()
schedule_store = ScheduleStore()
scnu_scraper = SCNUScraper()
auth_service = AuthService(user_store)
schedule_service = ScheduleService(schedule_store, scnu_scraper)
