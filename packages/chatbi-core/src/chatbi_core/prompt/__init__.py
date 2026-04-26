"""Dynamic system prompt assembly system.

Provides:
- PromptBuilder: assembles multi-section system prompts with caching
- ContextProvider: loads CLAUDE.md, git context, date, memory
- PromptSection: individual prompt section definitions
"""

from chatbi_core.prompt.sections import (
    PromptSection,
    STATIC_SECTIONS,
    DYNAMIC_SECTIONS,
    get_intro_section,
    get_system_section,
    get_tool_usage_section,
    get_tone_style_section,
    get_output_efficiency_section,
    get_environment_section,
    get_session_section,
)

from chatbi_core.prompt.context import (
    PromptContext,
    ContextProvider,
    get_date_context,
    get_git_context,
    get_claude_md_context,
    get_memory_context,
    get_project_context,
)

from chatbi_core.prompt.builder import (
    PromptBuilder,
    build_system_prompt,
    build_system_prompt_block,
    DYNAMIC_BOUNDARY,
)

__all__ = [
    "PromptSection",
    "STATIC_SECTIONS",
    "DYNAMIC_SECTIONS",
    "get_intro_section",
    "get_system_section",
    "get_tool_usage_section",
    "get_tone_style_section",
    "get_output_efficiency_section",
    "get_environment_section",
    "get_session_section",
    "PromptContext",
    "ContextProvider",
    "get_date_context",
    "get_git_context",
    "get_claude_md_context",
    "get_memory_context",
    "get_project_context",
    "PromptBuilder",
    "build_system_prompt",
    "build_system_prompt_block",
    "DYNAMIC_BOUNDARY",
]
