"""
Events module - logowanie zdarzeń do formatu JSON.

Zawiera:
- GameEvent: Dataclass reprezentująca zdarzenie
- EventType: Enum typów zdarzeń
- EventLogger: Klasa logująca zdarzenia
"""

from .event_logger import GameEvent, EventType, EventLogger

__all__ = ["GameEvent", "EventType", "EventLogger"]
