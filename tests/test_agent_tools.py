

from bot.config import load_runtime_config
from bot.llm import build_llm_stack
from bot.runtime.context import HandlerContext
from bot.runtime.tools import (
    AgentToolkit,
    parse_agent_response,
    run_tool_loop,
    tools_prompt_block,
)


def test_parse_agent_response_json() -> None:
    raw = '{"tool": "read_file", "args": {"path": "readme.md"}}'
    assert parse_agent_response(raw)["tool"] == "read_file"


def test_parse_done() -> None:
    assert parse_agent_response('{"done": true, "summary": "OK"}')["done"] is True


def test_toolkit_read_write(runtime_project) -> None:
    from bot.files.service import FileService

    fs = FileService.for_team(runtime_project, "alpha")
    fs.write_file("hello.txt", "Hallo Agent")

    ctx = HandlerContext(
        root=runtime_project,
        team_id="alpha",
        agent_id="worker-exec",
        role="worker",
        llm_stack=build_llm_stack(load_runtime_config(runtime_project)),
    )
    result = AgentToolkit(ctx).execute("read_file", {"path": "hello.txt"})
    assert result.ok
    assert "Hallo" in result.output


def test_run_tool_loop_done(runtime_project) -> None:
    config = load_runtime_config(runtime_project)
    ctx = HandlerContext(
        root=runtime_project,
        team_id="alpha",
        agent_id="worker-exec",
        role="worker",
        llm_stack=build_llm_stack(config),
    )
    summary = run_tool_loop(
        ctx,
        system_prompt="Antworte sofort mit done.",
        user_content="Test",
        task_category="coding",
        tools=frozenset(),
        max_steps=1,
    )
    assert "stub" in summary.lower() or summary


def test_tools_prompt_lists_tools() -> None:
    assert "read_file" in tools_prompt_block()
