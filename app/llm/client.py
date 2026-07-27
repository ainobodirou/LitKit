from typing import Any 
from models import model, messages, temperature
from litellm
class ModelService:


    async def generate(
            self,
            messages: list[dict[str,str]]
            model: str = model
    ) -> str: 
            response: Any = await acompletion(
                  model = model,
                  messages = messages,
                  temperature = temperature,
            )

    content = response.choices[0].message.content

    if not content:
          raise RuntimeError("Model returned empty response")
    return content 
