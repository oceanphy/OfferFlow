"""L9: Hooks — governance extension points for the diagnosis pipeline."""

from __future__ import annotations

from typing import Any, Callable

HookCallback = Callable[..., Any]


class HookRegistry:
    """Register callbacks for diagnosis lifecycle events.

    Available hooks:
        pre_diagnose  — called before diagnosis starts, receives (transcript)
        post_round    — called after each round, receives (round_index, round_data)
        post_report   — called after report generated, receives (report)
    """

    def __init__(self):
        self._hooks: dict[str, list[HookCallback]] = {
            "pre_diagnose": [],
            "post_round": [],
            "post_report": [],
        }

    def register(self, hook_name: str, callback: HookCallback) -> None:
        if hook_name not in self._hooks:
            raise ValueError(f"Unknown hook: {hook_name}. Available: {list(self._hooks)}")
        self._hooks[hook_name].append(callback)

    def remove(self, hook_name: str, callback: HookCallback) -> None:
        if hook_name in self._hooks:
            self._hooks[hook_name] = [
                cb for cb in self._hooks[hook_name] if cb != callback
            ]

    async def run(self, hook_name: str, **kwargs: Any) -> None:
        import asyncio

        for cb in self._hooks.get(hook_name, []):
            result = cb(**kwargs)
            if asyncio.iscoroutine(result):
                await result


# global registry
registry = HookRegistry()
