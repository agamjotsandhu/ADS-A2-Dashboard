"""Runtime configuration from environment variables (no secrets live in code)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    artifacts_dir: Path
    forecasts_path: Path
    allowed_origins: list[str]
    rate_limit_per_minute: int
    trust_proxy: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            artifacts_dir=Path(os.getenv("ARTIFACTS_DIR", REPO_ROOT / "ml" / "xgb" / "artifacts")),
            forecasts_path=Path(os.getenv(
                "FORECASTS_PATH", REPO_ROOT / "web" / "public" / "data" / "suburb_forecasts.json")),
            allowed_origins=[o.strip() for o in os.getenv(
                "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()],
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
            trust_proxy=os.getenv("TRUST_PROXY", "false").lower() in ("1", "true", "yes"),
        )
