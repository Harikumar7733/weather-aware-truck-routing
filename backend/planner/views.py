"""HTTP endpoints. Thin wrappers: parse → call a service → JSON."""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Callable

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .services import geocoding
from .services.heatmap import build_heatmap
from .services.http import UpstreamError, ValidationError
from .services.planner import plan_trip
from .services.validation import HeatmapRequest, PlanRequest

logger = logging.getLogger(__name__)


def api(view: Callable[[HttpRequest], dict | list]) -> Callable[[HttpRequest], JsonResponse]:
    @wraps(view)
    def wrapper(request: HttpRequest) -> JsonResponse:
        try:
            return JsonResponse(view(request), safe=False)
        except ValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except UpstreamError as exc:
            logger.warning("upstream failure: %s", exc)
            return JsonResponse({"error": str(exc)}, status=502)

    return wrapper


def _json_body(request: HttpRequest) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        raise ValidationError("Request body must be valid JSON.") from None
    if not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")
    return body


@require_GET
@api
def health(request: HttpRequest) -> dict:
    return {"status": "ok"}


@require_GET
@api
def geocode(request: HttpRequest) -> list:
    return [p.as_dict() for p in geocoding.search(request.GET.get("q", ""))]


@csrf_exempt
@require_POST
@api
def plan(request: HttpRequest) -> dict:
    return plan_trip(PlanRequest.parse(_json_body(request)))


@csrf_exempt
@require_POST
@api
def heatmap(request: HttpRequest) -> dict:
    return build_heatmap(HeatmapRequest.parse(_json_body(request)))
