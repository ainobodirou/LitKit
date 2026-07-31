import asyncio

from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.llm.models import create_assistant_models

async def main() -> None:
    settings = get_settings()
    models = create_assistant_models(settings)

    response = await models.supervisor.ainvoke(
        [
            HumanMessage(
                content=(
                    "Reply with exactly:" \
                    "LiteLLM connection succesful"
                )
            )
        ]
    )
    print(response.content)

if __name__ == "__main__":
    asyncio.run(main())