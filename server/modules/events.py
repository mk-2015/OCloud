from functools import wraps
from abc import ABC, abstractmethod
import os
import re

class Event():
    def __init__(self, user: str, path: str,
                event: str = "media.upload", event_tag: dict = {"tag-1": "file-upload"}):
        self.user = user 
        self.path = path
        self.event = event
        self.event_tag = event_tag

    def getobj():
        return {
            "user": self.user,
            "path": self.path,
            "event": self.event,
            "tags": self.event_tag
        }
