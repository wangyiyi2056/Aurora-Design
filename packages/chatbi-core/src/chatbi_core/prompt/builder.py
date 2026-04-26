"""System prompt builder with dynamic boundary for prompt caching.

Mirrors Claude-Code's getSystemPrompt() + SYSTEM_PROMPT_DYNAMIC_BOUNDARY pattern:
- Static sections before DYNAMIC_BOUNDARY can use global prompt cache
- Dynamic sections after DYNAMIC_BOUNDARY are per-session
- build_system_prompt_block() splits by boundary for cache_control blocks
"""

from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

from chatbi_core.prompt.sections import (
    PromptSection,
    STATIC_SECTIONS,
    get_environment_section,
    get_session_section,
    get_chart_vis_section,
)
from chatbi_core.prompt.context import ContextProvider, PromptContext

if TYPE_CHECKING:
    pass

# Boundary marker separating static (cacheable) from dynamic (per-session) content.
# Mirrors Claude-Code's SYSTEM_PROMPT_DYNAMIC_BOUNDARY in prompts.ts.
DYNAMIC_BOUNDARY = "__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__"


class PromptBuilder:
    """Assembles multi-section system prompts with caching boundary.

    Usage::

        builder = PromptBuilder(
            context_provider=ContextProvider(project_root="/path/to/project"),
            skill_registry=skill_registry,
            memory_manager=memory_manager,
        )
        prompt_array = builder.build()
        # prompt_array = [intro, system, ..., DYNAMIC_BOUNDARY, env, session, ...]

        prefix, suffix = builder.build_block()
        # prefix = intro + system + ... (everything before DYNAMIC_BOUNDARY)
        # suffix = env + session + ... (everything after DYNAMIC_BOUNDARY)
    """

    def __init__(
        self,
        context_provider: Optional[ContextProvider] = None,
        skill_registry=None,
        memory_manager=None,
        model_info: str = "",
        include_chart_vis: bool = True,
    ):
        self.context_provider = context_provider
        self.skill_registry = skill_registry
        self.memory_manager = memory_manager
        self.model_info = model_info
        self.include_chart_vis = include_chart_vis

        # Cache for assembled context
        self._context: Optional[PromptContext] = None

    def _assemble_context(self) -> PromptContext:
        if self._context is not None:
            return self._context
        if self.context_provider:
            self._context = self.context_provider.assemble()
        else:
            self._context = PromptContext()
        return self._context

    def build(self) -> List[str]:
        """Build the full system prompt as a list of strings.

        Each string is a section. The DYNAMIC_BOUNDARY marker separates
        static (cacheable) from dynamic (per-session) sections.
        """
        ctx = self._assemble_context()
        sections: List[str] = []

        # ── Static sections (cacheable) ──
        for section in STATIC_SECTIONS:
            if section.content:
                sections.append(section.content)

        # ── Dynamic boundary ──
        sections.append(DYNAMIC_BOUNDARY)

        # ── Dynamic sections (per-session) ──

        # Session guidance
        session_section = self._build_session_section()
        if session_section.content:
            sections.append(session_section.content)

        # Memory context
        if ctx.memory_context:
            sections.append(ctx.memory_context)

        # Environment info
        env_section = get_environment_section(
            project_root=ctx.project_root,
            platform=ctx.platform,
            shell=ctx.shell,
            python_version=ctx.python_version,
            model_info=self.model_info,
        )
        if env_section.content:
            sections.append(env_section.content)

        # Skills context
        if ctx.skills_context:
            sections.append(ctx.skills_context)

        # Chart visualization (ChatBI-specific)
        if self.include_chart_vis:
            chart_section = get_chart_vis_section()
            if chart_section.content:
                sections.append(chart_section.content)

        return sections

    def build_block(self) -> Tuple[str, str]:
        """Build prompt as (prefix, suffix) for cache_control blocks.

        prefix: Everything before DYNAMIC_BOUNDARY (cacheable)
        suffix: Everything after DYNAMIC_BOUNDARY (per-session)

        Returns:
            (prefix_str, suffix_str) tuple
        """
        prompt_array = self.build()
        try:
            boundary_idx = prompt_array.index(DYNAMIC_BOUNDARY)
        except ValueError:
            boundary_idx = len(prompt_array)

        prefix = "\n\n".join(prompt_array[:boundary_idx])
        suffix = "\n\n".join(prompt_array[boundary_idx + 1:])
        return prefix, suffix

    def build_single_string(self) -> str:
        """Build the full prompt as a single string."""
        prompt_array = self.build()
        return "\n\n".join(prompt_array)

    def _build_session_section(self) -> PromptSection:
        has_skills = self.skill_registry is not None
        skill_names = None
        if has_skills:
            try:
                skills = self.skill_registry.list_skills()
                skill_names = [
                    s.get("name", s) if isinstance(s, dict) else getattr(s, "name", str(s))
                    for s in skills[:30]
                ]
            except Exception:
                skill_names = []
        return get_session_section(
            has_skills=has_skills,
            has_agent=True,
            has_mcp=False,
            skill_names=skill_names,
        )

    def get_user_context(self) -> str:
        """Get user context for injection as <system-reminder> user message.

        Mirrors Claude-Code's user context injection pattern:
        CLAUDE.md + date prepended as a user message.
        """
        ctx = self._assemble_context()
        return ctx.to_user_context()

    def get_system_context(self) -> str:
        """Get system context for appending to system prompt.

        Mirrors Claude-Code's system context injection: git status.
        """
        ctx = self._assemble_context()
        return ctx.to_system_context()

    def clear_cache(self) -> None:
        """Clear cached context so next build() re-assembles."""
        self._context = None


def build_system_prompt(
    context_provider: Optional[ContextProvider] = None,
    skill_registry=None,
    memory_manager=None,
    model_info: str = "",
) -> List[str]:
    """Convenience function to build the full system prompt array."""
    builder = PromptBuilder(
        context_provider=context_provider,
        skill_registry=skill_registry,
        memory_manager=memory_manager,
        model_info=model_info,
    )
    return builder.build()


def build_system_prompt_block(
    context_provider: Optional[ContextProvider] = None,
    skill_registry=None,
    memory_manager=None,
    model_info: str = "",
) -> Tuple[str, str]:
    """Convenience function to build (prefix, suffix) for cache blocks."""
    builder = PromptBuilder(
        context_provider=context_provider,
        skill_registry=skill_registry,
        memory_manager=memory_manager,
        model_info=model_info,
    )
    return builder.build_block()
