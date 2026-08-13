from app.context.models import (
    ContextSource,
    TaskContextPolicy,
    TaskType
)

TASK_POLICIES: dict[TaskType, TaskContextPolicy] = {
    TaskType.GENERAL_CHAT: TaskContextPolicy(
        task_type=TaskType.GENERAL_CHAT,
        allowed_sources =(
            ContextSource.RECENT_MESSAGES,
            ContextSource.USER_MEMORY
        ),
        max_memories= 3,
        max_events = 0,
        max_sources = 2,
        model_role = "supervisor",
    ),
    TaskType.WORKOUT_LOG: TaskContextPolicy(
        task_type = TaskType.WORKOUT_LOG,
        allowed_sources = (
            ContextSource.ACTIVE_TASK,
            ContextSource.RECENT_EVENTS,
            ContextSource.USER_MEMORY
        ),
        max_memories= 3,
        max_events = 5,
        model_role = "specialist",
    ),
    TaskType.RESEARCH: TaskContextPolicy(
        task_type=TaskType.RESEARCH,
        allowed_sources = (
            ContextSource.KNOWLEDGE,
            ContextSource.RECENT_MESSAGES,
            ContextSource.ACTIVE_TASK
        ),
        max_sources = 8,
        model_role = "specialist",

    ),
    TaskType.CALENDAR: TaskContextPolicy(
        task_type=TaskType.RESEARCH,
        allowed_sources = (
            ContextSource.RECENT_MESSAGES,
            ContextSource.ACTIVE_TASK,
            ContextSource.USER_MEMORY,
        ),
        max_memories = 3,
        model_role = "supervisor",
    ),

}