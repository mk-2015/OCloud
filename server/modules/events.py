import asyncio
from collections import defaultdict
import logging

class Event():
    def __init__(self, user: str, path: str,
                event: str = "media.upload", event_tag: dict = {"tag-1": "file-upload"}):
        self.user = user 
        self.path = path
        self.event = event
        self.event_tag = event_tag

    def getobj(self):
        return {
            "user": self.user,
            "path": self.path,
            "event": self.event,
            "tags": self.event_tag
        }

_user_queues = defaultdict(asyncio.Queue)

async def addEvent(event: Event):
    await _user_queues[event.user].put(event)
    logging.info(f"Event '{event.event}' added to queue for user: {event.user}")

async def waitEvent(username: str, removeEventfromQueue=True) -> Event:
    event = await _user_queues[username].get()
    
    if not removeEventfromQueue:
        await _user_queues[username].put(event)
        
    logging.info(f"Event retrieved for user: {username} (removed: {removeEventfromQueue})")
    return event

async def popEvent(username: str):
    queue = _user_queues[username]
    if not queue.empty():
        await queue.get()
        logging.info(f"Event explicitly removed for user: {username}")
    else:
        logging.warning(f"Attempted to pop from empty queue for user: {username}")

async def getEventsBatch(username: str, max_batch=10) -> list[Event]:
    queue = _user_queues[username]
    events = []
    
    events.append(await queue.get())
    
    for _ in range(max_batch - 1):
        if queue.empty():
            break
        events.append(await queue.get())
        
    logging.info(f"Retrieved batch of {len(events)} events for user: {username}")
    return events

async def removeEvent(username: str, all=False, type="media.upload"):
    queue = _user_queues[username]
    temp_list = []
    
    while not queue.empty():
        temp_list.append(await queue.get())
    
    if all:
        new_list = [e for e in temp_list if e.event != type]
    else:
        new_list = []
        found = False
        for e in temp_list:
            if not found and e.event == type:
                found = True
                continue
            new_list.append(e)
            
    for e in new_list:
        await queue.put(e)
        
    logging.info(f"Processed removal for user: {username}, type: {type}, all: {all}")
