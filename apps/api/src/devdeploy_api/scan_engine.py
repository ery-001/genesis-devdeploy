"""Image vulnerability scanning — Trivy when available, else deterministic mock."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from devdeploy_api.models import VulnerabilityScan


@dataclass
class ScanResult:
    critical: int
    high: int
    medium: int
    low: int
    report: dict
    scanner: str


def _mock_scan(image_digest: str | None) -> ScanResult:
    seed = sum(ord(c) for c in (image_digest or "none")[:16])
    return ScanResult(
        critical=seed % 2,
        high=(seed // 3) % 4,
        medium=(seed // 5) % 8,
        low=(seed // 7) % 12,
        report={
            "Results": [
                {
                    "Target": image_digest or "local-image",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-MOCK",
                            "Severity": "MEDIUM",
                            "Title": "Mock finding for local demos",
                        }
                    ],
                }
            ]
        },
        scanner="mock",
    )


def run_trivy_or_mock(image_ref: str, image_digest: str | None) -> ScanResult:
    trivy = shutil.which("trivy")
    if not trivy:
        return _mock_scan(image_digest)
    try:
        proc = subprocess.run(
            [
                trivy,
                "image",
                "--quiet",
                "--format",
                "json",
                "--severity-exit-code",
                "0",
                image_ref,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            result = _mock_scan(image_digest)
            result.scanner = "mock-fallback"
            return result
        data = json.loads(proc.stdout)
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for block in data.get("Results") or []:
            for vuln in block.get("Vulnerabilities") or []:
                sev = (vuln.get("Severity") or "").upper()
                if sev in counts:
                    counts[sev] += 1
        return ScanResult(
            critical=counts["CRITICAL"],
            high=counts["HIGH"],
            medium=counts["MEDIUM"],
            low=counts["LOW"],
            report=data if isinstance(data, dict) else {"raw": data},
            scanner="trivy",
        )
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        result = _mock_scan(image_digest)
        result.scanner = "mock-fallback"
        return result


def persist_scan(
    db: DbSession,
    *,
    project_id,
    deployment_job_id,
    image_digest: str | None,
    image_ref: str,
) -> VulnerabilityScan:
    result = run_trivy_or_mock(image_ref, image_digest)
    row = VulnerabilityScan(
        project_id=project_id,
        deployment_job_id=deployment_job_id,
        image_digest=image_digest,
        status="completed",
        critical=result.critical,
        high=result.high,
        medium=result.medium,
        low=result.low,
        report_json=json.dumps(result.report)[:200_000],
        scanner=result.scanner,
    )
    db.add(row)
    db.flush()
    return row
