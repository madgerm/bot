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

    def _story_svc(team_id: str):
        from bot.story import StoryService

        return StoryService.for_team(root_path, team_id)

    @app.get("/teams/{team_id}/story", response_class=HTMLResponse)
    async def team_story_hub(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        db = _story_svc(team_id).db
        return templates.TemplateResponse(
            request,
            "team_story.html",
            {
                "user": user,
                "team_id": team_id,
                "meta": db.get_meta(),
                "chapter_count": len(db.list_chapters()),
                "character_count": len(db.list_characters()),
            },
        )

    @app.get("/teams/{team_id}/story/planner", response_class=HTMLResponse)
    async def team_story_planner(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        db = _story_svc(team_id).db
        return templates.TemplateResponse(
            request,
            "team_story_planner.html",
            {"user": user, "team_id": team_id, "meta": db.get_meta()},
        )

    @app.post("/teams/{team_id}/story/planner")
    async def team_story_planner_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        title: str = Form(...),
        genre: str = Form(""),
        setting: str = Form(""),
        tone: str = Form(""),
        main_characters: str = Form(""),
    ):
        require_team_access(team_id, user)
        chars = [c.strip() for c in main_characters.split(",") if c.strip()]
        _story_svc(team_id).db.ensure_story(
            title=title, genre=genre, setting=setting, tone=tone, main_characters=chars
        )
        return RedirectResponse(f"/teams/{team_id}/story/planner", status_code=302)

    @app.get("/teams/{team_id}/story/characters", response_class=HTMLResponse)
    async def team_story_characters(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        db = _story_svc(team_id).db
        return templates.TemplateResponse(
            request,
            "team_story_characters.html",
            {
                "user": user,
                "team_id": team_id,
                "characters": db.list_characters(),
            },
        )

    @app.post("/teams/{team_id}/story/characters")
    async def team_story_characters_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        char_id: str = Form(...),
        name: str = Form(...),
        role: str = Form(""),
        bio: str = Form(""),
        arc: str = Form(""),
        relationships: str = Form(""),
    ):
        require_team_access(team_id, user)
        rels = []
        for line in relationships.strip().splitlines():
            if "|" in line:
                to, typ = line.split("|", 1)
                rels.append({"to": to.strip(), "type": typ.strip()})
        _story_svc(team_id).db.save_character(
            char_id.strip().lower().replace(" ", "_"),
            {
                "name": name,
                "role": role,
                "background": bio,
                "arc": arc,
                "relationships": rels,
                "personality": {"traits": []},
            },
        )
        return RedirectResponse(f"/teams/{team_id}/story/characters", status_code=302)

    @app.get("/teams/{team_id}/story/world", response_class=HTMLResponse)
    async def team_story_world(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        db = _story_svc(team_id).db
        return templates.TemplateResponse(
            request,
            "team_story_world.html",
            {
                "user": user,
                "team_id": team_id,
                "orte": db.read_world_file("orte.md"),
                "regeln": db.read_world_file("regeln.md"),
                "timeline": db.read_world_file("timeline.md"),
            },
        )

    @app.post("/teams/{team_id}/story/world")
    async def team_story_world_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        file: str = Form(...),
        content: str = Form(...),
    ):
        require_team_access(team_id, user)
        from bot.story.db import StoryDBError

        try:
            _story_svc(team_id).db.write_world_file(file, content)
        except StoryDBError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(f"/teams/{team_id}/story/world", status_code=302)

    @app.get("/teams/{team_id}/story/scenes", response_class=HTMLResponse)
    async def team_story_scenes(
        request: Request,
        team_id: str,
        user: CurrentUser,
        chapter: str | None = None,
        scene: str | None = None,
    ):
        require_team_access(team_id, user)
        db = _story_svc(team_id).db
        chapters = db.list_chapters()
        scenes = db.list_scenes(chapter)
        scene_meta, scene_body, scene_version = None, "", 1
        if chapter and scene:
            try:
                scene_meta, scene_body = db.get_scene(chapter, scene)
                scene_version = int(scene_meta.get("version", 1))
            except Exception:
                pass
        return templates.TemplateResponse(
            request,
            "team_story_scenes.html",
            {
                "user": user,
                "team_id": team_id,
                "chapters": chapters,
                "scenes": scenes,
                "current_chapter": chapter,
                "current_scene": scene,
                "scene_meta": scene_meta,
                "scene_body": scene_body,
                "scene_version": scene_version,
            },
        )

    @app.post("/teams/{team_id}/story/scenes/chapter")
    async def team_story_add_chapter(
        request: Request, team_id: str, user: CurrentUser
    ):
        require_team_access(team_id, user)
        ch = _story_svc(team_id).db.add_chapter()
        return RedirectResponse(f"/teams/{team_id}/story/scenes?chapter={ch}", status_code=302)

    @app.post("/teams/{team_id}/story/scenes/new")
    async def team_story_new_scene(
        request: Request,
        team_id: str,
        user: CurrentUser,
        chapter_id: str = Form(...),
        title: str = Form(""),
        content: str = Form(""),
    ):
        require_team_access(team_id, user)
        info = _story_svc(team_id).db.add_scene(
            chapter_id, title=title, content=content
        )
        return RedirectResponse(
            f"/teams/{team_id}/story/scenes?chapter={chapter_id}&scene={info.scene_id}",
            status_code=302,
        )

    @app.post("/teams/{team_id}/story/scenes/save")
    async def team_story_save_scene(
        request: Request,
        team_id: str,
        user: CurrentUser,
        chapter_id: str = Form(...),
        scene_id: str = Form(...),
        content: str = Form(...),
        version: int = Form(...),
        status: str = Form("draft"),
    ):
        require_team_access(team_id, user)
        from bot.story.db import StoryDBError

        try:
            _story_svc(team_id).db.update_scene(
                chapter_id, scene_id, content, expected_version=version, status=status
            )
        except StoryDBError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RedirectResponse(
            f"/teams/{team_id}/story/scenes?chapter={chapter_id}&scene={scene_id}",
            status_code=302,
        )

    @app.get("/teams/{team_id}/story/plot", response_class=HTMLResponse)
    async def team_story_plot(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        import json as _json

        db = _story_svc(team_id).db
        plot = db.get_plot()
        return templates.TemplateResponse(
            request,
            "team_story_plot.html",
            {
                "user": user,
                "team_id": team_id,
                "plot": plot,
                "acts_json": _json.dumps(plot.get("acts", []), indent=2, ensure_ascii=False),
            },
        )

    @app.post("/teams/{team_id}/story/plot")
    async def team_story_plot_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        structure: str = Form("three_act"),
        notes: str = Form(""),
        acts_json: str = Form("[]"),
    ):
        require_team_access(team_id, user)
        import json as _json

        try:
            acts = _json.loads(acts_json)
        except _json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="acts_json ungültig") from exc
        _story_svc(team_id).db.save_plot(
            {"structure": structure, "acts": acts, "notes": notes}
        )
        return RedirectResponse(f"/teams/{team_id}/story/plot", status_code=302)

    @app.get("/teams/{team_id}/story/graph", response_class=HTMLResponse)
    async def team_story_graph(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        from bot.story.graph import relationships_mermaid

        db = _story_svc(team_id).db
        graph = db.build_relationship_graph()
        return templates.TemplateResponse(
            request,
            "team_story_graph.html",
            {
                "user": user,
                "team_id": team_id,
                "mermaid": relationships_mermaid(db),
                "graph": graph,
            },
        )

    @app.get("/teams/{team_id}/story/memory", response_class=HTMLResponse)
    async def team_story_memory(
        request: Request, team_id: str, user: CurrentUser, q: str = ""
    ):
        require_team_access(team_id, user)
        from bot.story import StoryMemoryService, StoryMemoryError

        results = None
        mem_error = None
        collections: dict[str, str] = {}
        if q:
            try:
                svc = StoryMemoryService.for_team(root_path, team_id)
                results = svc.search(q, collection="story", limit=10)
                collections = svc.ensure_collections()
            except StoryMemoryError as exc:
                mem_error = str(exc)
        return templates.TemplateResponse(
            request,
            "team_story_memory.html",
            {
                "user": user,
                "team_id": team_id,
                "query": q,
                "results": results,
                "mem_error": mem_error,
                "collections": collections,
            },
        )

    @app.post("/teams/{team_id}/story/memory/reindex")
    async def team_story_memory_reindex(
        request: Request, team_id: str, user: CurrentUser
    ):
        require_team_access(team_id, user)
        from bot.story import StoryMemoryService, StoryMemoryError

        try:
            counts = StoryMemoryService.for_team(root_path, team_id).reindex_all()
        except StoryMemoryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            f"/teams/{team_id}/story/memory?reindexed={counts}",
            status_code=302,
        )

    @app.get("/teams/{team_id}/story/review", response_class=HTMLResponse)
    async def team_story_review(
        request: Request,
        team_id: str,
        user: CurrentUser,
        chapter: str | None = None,
        scene: str | None = None,
    ):
        require_team_access(team_id, user)
        from bot.story.config import load_story_review_config

        db = _story_svc(team_id).db
        review_cfg = load_story_review_config(root_path, team_id)
        chapters = db.list_chapters()
        scenes = db.list_scenes(chapter) if chapter else []
        last_results = None
        return templates.TemplateResponse(
            request,
            "team_story_review.html",
            {
                "user": user,
                "team_id": team_id,
                "issues": db.list_review_issues(),
                "checkers": review_cfg.checkers,
                "chapters": chapters,
                "scenes": scenes,
                "current_chapter": chapter,
                "current_scene": scene,
                "last_results": last_results,
            },
        )

    @app.post("/teams/{team_id}/story/review/parallel")
    async def team_story_review_parallel(
        request: Request,
        team_id: str,
        user: CurrentUser,
        chapter_id: str = Form(...),
        scene_id: str = Form(...),
    ):
        require_team_access(team_id, user)
        from bot.story import StoryReviewRunner, StoryReviewError

        try:
            results = StoryReviewRunner.for_team(root_path, team_id).review_scene_parallel(
                chapter_id, scene_id
            )
        except StoryReviewError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        import json as _json

        return templates.TemplateResponse(
            request,
            "team_story_review.html",
            {
                "user": user,
                "team_id": team_id,
                "issues": _story_svc(team_id).db.list_review_issues(limit=30),
                "checkers": load_story_review_config(root_path, team_id).checkers,
                "chapters": _story_svc(team_id).db.list_chapters(),
                "scenes": _story_svc(team_id).db.list_scenes(chapter_id),
                "current_chapter": chapter_id,
                "current_scene": scene_id,
                "last_results": [r.to_dict() for r in results],
            },
        )

    @app.post("/teams/{team_id}/story/review")
    async def team_story_review_add(
        request: Request,
        team_id: str,
        user: CurrentUser,
        checker: str = Form(...),
        severity: str = Form("info"),
        message: str = Form(...),
        chapter_id: str = Form(""),
        scene_id: str = Form(""),
    ):
        require_team_access(team_id, user)
        _story_svc(team_id).db.add_review_issue(
            checker=checker,
            severity=severity,
            message=message,
            chapter_id=chapter_id or None,
            scene_id=scene_id or None,
        )
        return RedirectResponse(f"/teams/{team_id}/story/review", status_code=302)

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
