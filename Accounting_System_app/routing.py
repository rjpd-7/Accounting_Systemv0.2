from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/messages/$', consumers.MessagingConsumer.as_asgi()),
    re_path(r'ws/account-codes/$', consumers.AccountCodeConsumer.as_asgi()),
    re_path(r'ws/journal-codes/$', consumers.JournalCodeConsumer.as_asgi()),
]
