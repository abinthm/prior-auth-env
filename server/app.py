from __future__ import annotations

import ast
import json
from urllib.parse import parse_qs

from openenv.core.env_server import create_app
from fastapi.responses import JSONResponse

from models import PriorAuthAction, PriorAuthObservation
from server.prior_auth_environment import PriorAuthEnvironment


app = create_app(
    PriorAuthEnvironment,
    PriorAuthAction,
    PriorAuthObservation,
    env_name="prior_auth_env",
)

_http_env = PriorAuthEnvironment()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": "prior-auth-env"}


def _coerce_to_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                return {}
    return {}


def _parse_payload(body: bytes) -> dict:
    if not body:
        return {}

    text = body.decode("utf-8", errors="ignore").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        form = parse_qs(text, keep_blank_values=True)
        if form:
            flattened = {key: values[-1] if values else "" for key, values in form.items()}
            payload = {
                "action_type": flattened.get("action_type", flattened.get("Action Type", "")),
                "params": _coerce_to_dict(flattened.get("params", flattened.get("Params", "{}"))),
            }
            task_name = flattened.get("task_name", flattened.get("Task Name", ""))
            if task_name:
                payload["task_name"] = task_name
            return payload

        try:
            parsed = ast.literal_eval(text)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            return {}


@app.middleware("http")
async def health_compatibility_middleware(request, call_next):
    if request.url.path == "/":
        return JSONResponse({"status": "ok", "service": "prior-auth-env"})

    if request.url.path == "/health":
        return JSONResponse({"status": "ok"})

    if request.url.path == "/reset" and request.method.upper() == "POST":
        payload = _parse_payload(await request.body())
        observation = _http_env.reset(**payload)
        return JSONResponse(
            {
                "observation": observation.model_dump(),
                "reward": observation.reward,
                "done": observation.done,
            }
        )

    if request.url.path == "/step" and request.method.upper() == "POST":
        payload = _parse_payload(await request.body())
        action = PriorAuthAction(
            action_type=payload.get("action_type", ""),
            params=_coerce_to_dict(payload.get("params", {})),
        )
        observation = _http_env.step(action)
        return JSONResponse(
            {
                "observation": observation.model_dump(),
                "reward": observation.reward,
                "done": observation.done,
            }
        )

    return await call_next(request)


def main(host: str = "0.0.0.0", port: int = 7860):
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
