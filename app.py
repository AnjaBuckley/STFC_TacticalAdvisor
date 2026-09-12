"""STFC Tactical Advisor: local FastAPI app with a custom browser frontend."""

import asyncio
import copy
import json
import re
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

import paths
from engine.abilities import load_abilities
from optimizer.crew_optimizer import _below_deck_slot_count, find_optimal_crew
from service import (
    PROFILE_LOCK,
    TASKS,
    catalog,
    mission_target,
    read_profile,
    save_profile,
    validate_profile,
)
from sheet_sync import SheetSync


@asynccontextmanager
async def lifespan(app):
    app.state.sheet_sync = SheetSync()
    app.state.sheet_sync.start()
    try:
        yield
    finally:
        await asyncio.to_thread(app.state.sheet_sync.stop)


app = FastAPI(title="STFC Tactical Advisor", version="3.0.0", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"],
)
TOKEN = secrets.token_urlsafe(32)


@app.middleware("http")
async def local_writes(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        if request.headers.get("x-stfc-token") != TOKEN:
            return JSONResponse(
                {"detail": "Reload the console to renew the local session."}, 403
            )
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse(
                {"detail": "Requests must originate from this local console."}, 403
            )
        if int(request.headers.get("content-length", 0)) > 12 * 1024 * 1024:
            return JSONResponse({"detail": "File exceeds the 12 MB upload limit."}, 413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TargetStats(StrictModel):
    hp: float | None = Field(default=None, gt=0, le=1e20)
    base_damage: float | None = Field(default=None, ge=0, le=1e20)
    armor_piercing: float | None = Field(default=None, ge=0, le=1e18)
    shield_piercing: float | None = Field(default=None, ge=0, le=1e18)
    accuracy: float | None = Field(default=None, ge=0, le=1e18)
    crit_chance: float | None = Field(default=None, ge=0, le=1)
    crit_multiplier: float | None = Field(default=None, ge=1, le=1e9)
    iso_defense: float | None = Field(default=None, ge=0, le=1e9)
    isolytic_damage_bonus: float | None = Field(default=None, ge=0, le=1e9)
    apex_barrier: float | None = Field(default=None, ge=0, le=1e12)
    apex_shred: float | None = Field(default=None, ge=0, le=1)
    hyperthermic_decay_fraction: float | None = Field(default=None, ge=0, le=1)


class RecommendationRequest(StrictModel):
    task_type: str = "pve_hostile"
    target_name: str = "Gorn Hunter"
    level: int = Field(default=60, ge=1, le=100)
    ship_name: str | None = None
    top_n: int = Field(default=3, ge=1, le=10)
    enemy_class: Literal["Battleship", "Explorer", "Interceptor"] = "Battleship"
    target_stats: TargetStats | None = None
    excluded_officers: list[str] = Field(default_factory=list, max_length=1000)


class ProfileUpdate(StrictModel):
    profile: dict
    revision: str


class SheetPreviewRequest(StrictModel):
    url: str = Field(min_length=20, max_length=1000)


class SheetSyncRequest(SheetPreviewRequest):
    enabled: bool = True


@app.get("/api/sync")
def sync_status(request: Request):
    return request.app.state.sheet_sync.status()


@app.put("/api/sync")
def configure_sync(body: SheetSyncRequest, request: Request):
    try:
        return request.app.state.sheet_sync.configure(body.url, body.enabled)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/sync/run")
def run_sync(request: Request):
    return request.app.state.sheet_sync.run()


@app.get("/api/bootstrap")
def bootstrap():
    profile, revision = read_profile()
    return {
        "profile": profile,
        "revision": revision,
        "token": TOKEN,
        **catalog(),
        "abilities": load_abilities(),
        "rules": json.loads(
            paths.resource_path("data", "rules.json").read_text(encoding="utf-8")
        ),
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "3.0.0",
        "desktop_instance": getattr(app.state, "desktop_instance", None),
    }


@app.put("/api/profile")
def update_profile(body: ProfileUpdate):
    try:
        revision = save_profile(body.profile, body.revision)
        return {
            "revision": revision,
            "message": "Account saved. A backup of the previous profile was created.",
        }
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/profile/export")
def export_profile():
    profile, _ = read_profile()
    return JSONResponse(
        profile,
        headers={"Content-Disposition": 'attachment; filename="stfc-account.json"'},
    )


@app.post("/api/recommend")
def recommend(body: RecommendationRequest):
    if body.task_type not in TASKS:
        raise HTTPException(422, "Choose a supported mission type.")
    profile, revision = read_profile()
    try:
        validate_profile(profile)
        profile = copy.deepcopy(profile)
        if body.ship_name:
            profile["ships"] = [
                s for s in profile["ships"] if s["name"] == body.ship_name
            ]
        blocked = set(body.excluded_officers)
        profile["officers"] = [
            o for o in profile["officers"] if o["name"] not in blocked
        ]
        target = mission_target(
            body.task_type,
            body.target_name,
            body.level,
            body.enemy_class,
            (
                body.target_stats.model_dump(exclude_none=True)
                if body.target_stats
                else {}
            ),
        )
        if (
            body.task_type in {"pve_academy_drone", "duo_wave_defense"}
            and profile["ops_level"] < 61
        ):
            raise ValueError("Academy content requires Operations level 61 or above.")
        results = find_optimal_crew(
            profile, {"task_type": body.task_type, "target": target}, body.top_n
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    ships = {s["name"]: s for s in profile["ships"]}
    for result in results:
        result["ship_details"] = ships[result["ship"]]
        result["below_deck_slots"] = _below_deck_slot_count(ships[result["ship"]])
    warnings = [
        "Rankings use a heuristic shortlist and estimated combat, not a complete STFC battle replay.",
        "Ship research, officer-to-ship stat conversion, shields and firing order need battle-log calibration.",
    ]
    if not target.get("real_hostile"):
        warnings.append(
            "This target uses curated or manually entered stats, not a verified level-specific hostile record."
        )
    elif target["real_hostile"]["level"] != body.level:
        warnings.append(
            f"Closest available hostile level is {target['real_hostile']['level']}; requested level was {body.level}."
        )
    if target.get("hyperthermic_decay") and not target.get(
        "hyperthermic_decay_fraction"
    ):
        warnings.append(
            "Hyperthermic Decay magnitude is unknown. Enter its per-round fraction in Target stats to model it."
        )
    if any(r["critical_mitigation"]["legacy_override"] for r in results):
        warnings.append(
            "Legacy Critical Mitigation percentages are active. Enter actual in-game points in Account to migrate."
        )
    if body.task_type in {
        "wave_defense",
        "duo_wave_defense",
        "galactic_anomaly",
        "dreadnought",
        "pvp_station",
        "station_raid",
    }:
        warnings.append(
            "This is an individual encounter estimate. Team coordination, station platforms, event modifiers and multi-wave persistence are not simulated."
        )
    if results and not any(r["simulation"]["kill_probability"] > 0 for r in results):
        warnings.insert(
            0,
            "No candidate defeated this target in the current model. Check the ship/target "
            "stats and unmodelled abilities, or choose a lower target level.",
        )
    counter = None
    if body.task_type == "pvp":
        from optimizer.pvp_logic import suggest_pvp_counter

        counter = suggest_pvp_counter(body.enemy_class, profile["officers"])
    return {
        "pvp_counter": counter,
        "recommendations": results,
        "target": target,
        "warnings": warnings,
        "profile_revision": revision,
        "task_type": body.task_type,
    }


@app.post("/api/import/preview")
def preview_import(
    kind: Literal["research", "officers", "profile"],
    file: Annotated[UploadFile, File()],
):
    raw = file.file.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "Choose a file smaller than 12 MB.")
    with PROFILE_LOCK:
        profile, revision = read_profile()
        try:
            if kind == "research":
                from ingest.research_csv import (
                    apply_to_profile,
                    compute_research_buffs,
                    parse_research_csv,
                )

                rows = parse_research_csv(raw)
                if not rows:
                    raise ValueError(
                        "No research rows found. Use a Spocks.club research CSV export."
                    )
                report = compute_research_buffs(rows)
                updated, diff = apply_to_profile(
                    copy.deepcopy(profile), report["buckets"]
                )
            elif kind == "officers":
                from ingest.officer_tool_sheet import (
                    apply_to_profile,
                    fetch_workbook,
                    parse_bonuses,
                    parse_roster,
                )

                workbook = fetch_workbook(raw)
                try:
                    updated, diff = apply_to_profile(
                        copy.deepcopy(profile),
                        parse_bonuses(workbook),
                        parse_roster(workbook),
                    )
                finally:
                    workbook.close()
            else:
                updated = json.loads(raw)
                diff = [
                    "Replace this account with the uploaded profile. The current account will be backed up."
                ]
            validate_profile(updated)
        except Exception as exc:
            raise HTTPException(
                422, f"Could not read this file: {str(exc)[:200]}"
            ) from exc
    return {
        "profile": updated,
        "revision": revision,
        "diff": diff,
        "message": "Preview only. Apply changes to save this account.",
    }


@app.post("/api/import/sheet-preview")
def preview_sheet(body: SheetPreviewRequest):
    parsed = urlparse(body.url)
    match = re.fullmatch(r"/spreadsheets/d/([a-zA-Z0-9_-]{20,})(?:/.*)?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "docs.google.com" or not match:
        raise HTTPException(
            422,
            "Use a Google Sheets URL beginning https://docs.google.com/spreadsheets/d/.",
        )
    from ingest.officer_tool_sheet import (
        apply_to_profile,
        fetch_workbook,
        parse_bonuses,
        parse_roster,
    )

    try:
        workbook = fetch_workbook(match.group(1))
        try:
            bonuses, roster = parse_bonuses(workbook), parse_roster(workbook)
        finally:
            workbook.close()
        profile, revision = read_profile()
        updated, diff = apply_to_profile(copy.deepcopy(profile), bonuses, roster)
        validate_profile(updated)
    except Exception as exc:
        raise HTTPException(
            422, f"Could not read the Officers Tool sheet: {str(exc)[:200]}"
        ) from exc
    return {
        "profile": updated,
        "revision": revision,
        "diff": diff,
        "message": "Preview only. Apply saves exactly these imported values without fetching again.",
    }


@app.get("/")
def index():
    return FileResponse(paths.resource_path("web", "index.html"))


app.mount("/assets", StaticFiles(directory=paths.resource_path("web")), name="assets")
