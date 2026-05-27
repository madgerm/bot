"""Phase-3 Web-Routes: Tasks, Agents, Files, Git, Story, Media, Crawl."""

from __future__ import annotations

from pathlib import Path

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.web.auth import CurrentUser, require_admin, require_team_access


def register_phase3_routes(app, templates: Jinja2Templates, root_path: Path) -> None:
    @app.get("/teams/{team_id}/tasks", response_class=HTMLResponse)
    async def team_tasks_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.tasks import TaskService

        tasks = TaskService.for_team(root_path, team_id).store.list_tasks()
        grouped = {"todo": [], "in_progress": [], "done": []}
        for t in tasks:
            if t.status in grouped:
                grouped[t.status].append(t)
        return templates.TemplateResponse(
            request,
            "team_tasks.html",
            {"user": user, "team_id": team_id, "grouped": grouped},
        )

    @app.post("/teams/{team_id}/tasks/create")
    async def team_tasks_create(
        request: Request,
        team_id: str,
        user: CurrentUser,
        title: str = Form(...),
        description: str = Form(""),
        assignee_agent: str = Form(""),
    ):
        require_team_access(team_id, user)
        from bot.tasks import TaskService

        TaskService.for_team(root_path, team_id).create(
            title=title,
            description=description,
            assignee_agent=assignee_agent or None,
            created_by=user.username,
        )
        return RedirectResponse(f"/teams/{team_id}/tasks", status_code=302)

    @app.post("/teams/{team_id}/tasks/{task_id}/status")
    async def team_tasks_status(
        request: Request,
        team_id: str,
        task_id: str,
        user: CurrentUser,
        status: str = Form(...),
    ):
        require_team_access(team_id, user)
        from bot.tasks import TaskService, TaskServiceError

        try:
            TaskService.for_team(root_path, team_id).move(task_id, status)  # type: ignore[arg-type]
        except TaskServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/tasks", status_code=302)

    @app.get("/teams/{team_id}/agents", response_class=HTMLResponse)
    async def team_agents_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.agents_mgmt import AgentManager

        agents = AgentManager(root_path).list_agents(team_id)
        return templates.TemplateResponse(
            request,
            "team_agents.html",
            {"user": user, "team_id": team_id, "agents": agents, "error": None},
        )

    @app.post("/teams/{team_id}/agents/create")
    async def team_agents_create(
        request: Request,
        team_id: str,
        user: CurrentUser,
        agent_id: str = Form(...),
        role: str = Form("worker"),
    ):
        require_team_access(team_id, user)
        from bot.agents_mgmt import AgentManager, AgentManagerError

        try:
            AgentManager(root_path).create_agent(team_id, agent_id=agent_id.strip(), role=role)
        except AgentManagerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/agents", status_code=302)

    @app.post("/teams/{team_id}/agents/{agent_id}/delete")
    async def team_agents_delete(
        request: Request, team_id: str, agent_id: str, user: CurrentUser
    ):
        require_team_access(team_id, user)
        from bot.agents_mgmt import AgentManager, AgentManagerError

        try:
            AgentManager(root_path).delete_agent(team_id, agent_id)
        except AgentManagerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/agents", status_code=302)

    @app.get("/teams/{team_id}/files", response_class=HTMLResponse)
    async def team_files_page(
        request: Request, team_id: str, user: CurrentUser, path: str = ""
    ):
        require_team_access(team_id, user)
        from bot.files import FileService, FileServiceError

        fs = FileService.for_team(root_path, team_id)
        try:
            entries = fs.list_dir(path)
        except FileServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        content = None
        edit_path = request.query_params.get("edit")
        if edit_path:
            try:
                content = fs.read_file(edit_path)
            except FileServiceError:
                content = None
        return templates.TemplateResponse(
            request,
            "team_files.html",
            {
                "user": user,
                "team_id": team_id,
                "path": path,
                "entries": entries,
                "edit_path": edit_path,
                "content": content,
            },
        )

    @app.post("/teams/{team_id}/files/save")
    async def team_files_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        file_path: str = Form(...),
        content: str = Form(...),
    ):
        require_team_access(team_id, user)
        from bot.files import FileService, FileServiceError

        try:
            FileService.for_team(root_path, team_id).write_file(file_path, content)
        except FileServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            f"/teams/{team_id}/files?edit={file_path}", status_code=302
        )

    @app.get("/teams/{team_id}/git", response_class=HTMLResponse)
    async def team_git_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.git_svc import GitService, GitServiceError

        status_text = ""
        log_text = ""
        git_error = None
        try:
            svc = GitService.for_team(root_path, team_id)
            status_text = svc.status()
            log_text = svc.log()
        except GitServiceError as exc:
            git_error = str(exc)
        return templates.TemplateResponse(
            request,
            "team_git.html",
            {
                "user": user,
                "team_id": team_id,
                "status": status_text,
                "log": log_text,
                "git_error": git_error,
            },
        )

    @app.post("/teams/{team_id}/git/commit")
    async def team_git_commit(
        request: Request,
        team_id: str,
        user: CurrentUser,
        message: str = Form(...),
    ):
        require_team_access(team_id, user)
        from bot.git_svc import GitService, GitServiceError

        try:
            GitService.for_team(root_path, team_id).commit(message)
        except GitServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/git", status_code=302)

    @app.get("/teams/{team_id}/story", response_class=HTMLResponse)
    async def team_story_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.story import StoryService

        svc = StoryService.for_team(root_path, team_id)
        return templates.TemplateResponse(
            request,
            "team_story.html",
            {
                "user": user,
                "team_id": team_id,
                "characters": svc.store.list_characters(),
                "worlds": svc.store.list_worlds(),
                "scenes": svc.store.list_scenes(),
            },
        )

    @app.post("/teams/{team_id}/story/character")
    async def team_story_character(
        request: Request,
        team_id: str,
        user: CurrentUser,
        name: str = Form(...),
        bio: str = Form(""),
    ):
        require_team_access(team_id, user)
        from bot.story import StoryService

        StoryService.for_team(root_path, team_id).store.save_character(name, bio)
        return RedirectResponse(f"/teams/{team_id}/story", status_code=302)

    @app.post("/teams/{team_id}/story/world")
    async def team_story_world(
        request: Request,
        team_id: str,
        user: CurrentUser,
        name: str = Form(...),
        description: str = Form(""),
    ):
        require_team_access(team_id, user)
        from bot.story import StoryService

        StoryService.for_team(root_path, team_id).store.save_world(name, description)
        return RedirectResponse(f"/teams/{team_id}/story", status_code=302)

    @app.post("/teams/{team_id}/story/scene")
    async def team_story_scene(
        request: Request,
        team_id: str,
        user: CurrentUser,
        title: str = Form(...),
        content: str = Form(""),
    ):
        require_team_access(team_id, user)
        from bot.story import StoryService

        StoryService.for_team(root_path, team_id).store.save_scene(title, content)
        return RedirectResponse(f"/teams/{team_id}/story", status_code=302)

    @app.get("/teams/{team_id}/media", response_class=HTMLResponse)
    async def team_media_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        return templates.TemplateResponse(
            request,
            "team_media.html",
            {"user": user, "team_id": team_id, "result": None, "error": None},
        )

    @app.post("/teams/{team_id}/media/image")
    async def team_media_image(
        request: Request,
        team_id: str,
        user: CurrentUser,
        prompt: str = Form(...),
    ):
        require_team_access(team_id, user)
        from bot.media import MediaService, MediaServiceError

        result = None
        error = None
        try:
            result = MediaService.for_team(root_path, team_id).generate_image(prompt)
        except MediaServiceError as exc:
            error = str(exc)
        return templates.TemplateResponse(
            request,
            "team_media.html",
            {"user": user, "team_id": team_id, "result": result, "error": error},
        )

    @app.get("/teams/{team_id}/crawl", response_class=HTMLResponse)
    async def team_crawl_page(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        return templates.TemplateResponse(
            request,
            "team_crawl.html",
            {"user": user, "team_id": team_id, "results": None, "error": None},
        )

    @app.post("/teams/{team_id}/crawl/run")
    async def team_crawl_run(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.crawl import CrawlService, CrawlServiceError

        results = None
        error = None
        try:
            svc = CrawlService.for_team(root_path, team_id)
            results = svc.crawl_all_configured()
            for pages in results.values():
                svc.index_to_qdrant(pages)
        except (CrawlServiceError, Exception) as exc:
            error = str(exc)
        return templates.TemplateResponse(
            request,
            "team_crawl.html",
            {"user": user, "team_id": team_id, "results": results, "error": error},
        )

    @app.get("/admin/deploy", response_class=HTMLResponse)
    async def admin_deploy_page(request: Request, user: CurrentUser):
        require_admin(user)
        from bot.config import load_runtime_config

        cfg = load_runtime_config(root_path)
        dep = cfg.system.deployment
        return templates.TemplateResponse(
            request,
            "admin_deploy.html",
            {"user": user, "deployment": dep},
        )

    @app.post("/admin/deploy/{team_id}")
    async def admin_deploy_generate(
        request: Request, team_id: str, user: CurrentUser
    ):
        require_admin(user)
        from bot.deploy import DeployService

        paths = DeployService(root_path).write_artifacts(team_id)
        return templates.TemplateResponse(
            request,
            "admin_deploy.html",
            {
                "user": user,
                "deployment": None,
                "generated": paths,
                "team_id": team_id,
            },
        )
