from assistant.prompts import SUPERVISOR_PROMPT
from langchain.agents import create_agent
from app.llm import model
from assistant.agents.calendar_agent import schedule_event


supervisor_agent = create_agent(
    model,
    tools = [schedule_event],
    system_prompt = SUPERVISOR_PROMPT
)

