from dataclasses import dataclass
from typing import Literal, Protocol

@dataclass(frozen=True)
class UserMessage:
    channel: Literal["telegram"]
    sender_id: str
    conversation_id: str
    text: str

class MessageSender(Protocol):
    async def send_text(
            self,
            *,
            recepient_id: str,
            text:str,
    ) -> None : None