from fastapi import APIRouter, Depends, status 

from app.dependancies import get_assistant_service 
from app.schemas.telegram import TelegramUpdate 

router = APIRouter()

@router.post("/webhook", status_code = status.HTTP_200_OK,
)
async def tg_webhook(
    update: TelegramUpdate,
    assistant: AssistantService = Depends(get_assistant_service)
) -> dict[str,str]:
    await assistant.handle_tg_update(update)
    return {"status":"OK"}
