from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REF_PATTERN = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end].strip()
    data = yaml.safe_load(block)
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_value(value: Any, tokens: dict[str, Any]) -> Any:
    if isinstance(value, str):
        prev = None
        current = value
        while prev != current:
            prev = current

            def repl(match: re.Match[str]) -> str:
                ref = match.group(1)
                parts = ref.split(".")
                node: Any = tokens
                for part in parts:
                    if not isinstance(node, dict) or part not in node:
                        return match.group(0)
                    node = node[part]
                if isinstance(node, dict):
                    return match.group(0)
                return str(node)

            current = _REF_PATTERN.sub(repl, current)
        return current
    if isinstance(value, dict):
        return {k: _resolve_value(v, tokens) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, tokens) for item in value]
    return value


def _resolve_tokens(raw: dict[str, Any]) -> dict[str, Any]:
    resolved = _resolve_value(raw, raw)
    if not isinstance(resolved, dict):
        return {}
    return resolved


@lru_cache(maxsize=1)
def load_design_tokens() -> dict[str, Any]:
    """Tokens resueltos: base Cal.com + capa de marca Sanzar Space.

    Los tokens viven en el frontmatter de dos ficheros Markdown, no en Python,
    para que el documento de diseño y el código no puedan divergir: cambiar un
    color es editar el .md.
    """
    cal = _parse_frontmatter(_REPO_ROOT / "DESIGN-cal.md")
    space = _parse_frontmatter(_REPO_ROOT / "DESIGN-space.md")
    return _resolve_tokens(_deep_merge(cal, space))


def color(name: str, *, default: str = "#000000") -> str:
    colors = load_design_tokens().get("colors", {})
    value = colors.get(name, default)
    return str(value)


def rounded(name: str, *, default: str = "8px") -> str:
    radii = load_design_tokens().get("rounded", {})
    value = radii.get(name, default)
    return str(value)


def spacing(name: str, *, default: str = "16px") -> str:
    spaces = load_design_tokens().get("spacing", {})
    value = spaces.get(name, default)
    return str(value)


def typography(name: str) -> dict[str, Any]:
    typo = load_design_tokens().get("typography", {})
    block = typo.get(name, {})
    return block if isinstance(block, dict) else {}


def component(name: str) -> dict[str, Any]:
    components = load_design_tokens().get("components", {})
    block = components.get(name, {})
    return block if isinstance(block, dict) else {}


_MOTION_DEFAULTS: dict[str, str] = {
    "duration-instant": "100ms",
    "duration-fast": "160ms",
    "duration-base": "200ms",
    "duration-slow": "260ms",
    "ease-out": "cubic-bezier(0.23, 1, 0.32, 1)",
    "ease-in-out": "cubic-bezier(0.77, 0, 0.175, 1)",
    "stagger-step": "40ms",
}


def motion(name: str) -> str:
    """Duración o curva de easing del sistema de movimiento (ver DESIGN-space.md)."""
    tokens = load_design_tokens().get("motion", {})
    return str(tokens.get(name, _MOTION_DEFAULTS.get(name, "200ms")))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def mix_hex(base: str, target: str, ratio: float) -> str:
    r1, g1, b1 = _hex_to_rgb(base)
    r2, g2, b2 = _hex_to_rgb(target)
    return _rgb_to_hex(
        int(r1 + (r2 - r1) * ratio),
        int(g1 + (g2 - g1) * ratio),
        int(b1 + (b2 - b1) * ratio),
    )


def pastel_triplet(base_hex: str) -> tuple[str, str, str]:
    """Return (background, border, foreground) for status chips."""
    bg = mix_hex("#ffffff", base_hex, 0.14)
    border = mix_hex("#ffffff", base_hex, 0.42)
    fg = base_hex
    return bg, border, fg


def css_variables() -> str:
    """Generate :root CSS custom properties from design tokens."""
    c = load_design_tokens().get("colors", {})
    hairline = c.get("hairline", "#e5e7eb")
    brand = color("brand-accent")
    brand_hover = color("brand-accent-hover")
    brand_soft = color("brand-accent-soft")
    brand_contrast = color("brand-accent-contrast")

    canvas = c.get("canvas", "#ffffff")
    surface_soft = c.get("surface-soft", "#f8f9fa")
    surface_card = c.get("surface-card", "#f5f5f5")
    hairline_soft = c.get("hairline-soft", "#f3f4f6")
    ink = c.get("ink", "#111111")
    body = c.get("body", "#374151")
    muted = c.get("muted", "#6b7280")
    primary = c.get("primary", "#111111")
    primary_active = c.get("primary-active", "#242424")

    success_bg, success_border, _ = pastel_triplet(color("semantic-success"))
    warning_bg, warning_border, _ = pastel_triplet(color("semantic-warning"))
    error_bg, error_border, error_fg = pastel_triplet(color("semantic-error"))
    info_bg, info_border, _ = pastel_triplet(color("semantic-info"))
    purple_bg, purple_border, _ = pastel_triplet(color("semantic-purple"))
    neutral_bg = surface_card
    neutral_border = hairline
    ink = c.get("ink", "#111111")
    body = c.get("body", "#374151")
    muted = c.get("muted", "#6b7280")
    primary = c.get("primary", "#111111")
    primary_active = c.get("primary-active", "#242424")

    bucket_past = color("bucket-past")
    bucket_today = color("bucket-today")
    bucket_future = color("bucket-future")

    radius_md = rounded("md")
    radius_lg = rounded("lg")
    spacing_sm = spacing("sm")
    spacing_md = spacing("md")
    spacing_lg = spacing("lg")

    lines = [
        "        :root {",
        "          /* Typography */",
        "          --ui-font: 'Inter', ui-sans-serif, system-ui, sans-serif;",
        "          /* Surfaces — from DESIGN-cal */",
        f"          --ui-bg-page: {canvas};",
        f"          --ui-bg-elevated: {canvas};",
        f"          --ui-sidebar: {surface_soft};",
        f"          --ui-border: {hairline};",
        f"          --ui-border-strong: {c.get('surface-strong', '#e5e7eb')};",
        f"          --ui-text: {ink};",
        f"          --ui-text-muted: {muted};",
        f"          --ui-text-body: {body};",
        f"          --ui-surface-card: {surface_card};",
        f"          --ui-surface-soft: {surface_soft};",
        f"          --ui-hairline-soft: {hairline_soft};",
        "          /* Brand — from DESIGN-sanzar */",
        f"          --ui-accent: {brand};",
        f"          --ui-accent-hover: {brand_hover};",
        f"          --ui-accent-contrast: {brand_contrast};",
        f"          --sanzar-green: {brand};",
        f"          --sanzar-green-soft: {brand_soft};",
        "          --sanzar-border: var(--ui-border);",
        "          --sanzar-text: var(--ui-text);",
        "          /* Cal primary (high-action CTA) */",
        f"          --ui-primary-strong: {primary};",
        f"          --ui-primary-strong-active: {primary_active};",
        f"          --ui-primary-strong-contrast: {c.get('on-primary', '#ffffff')};",
        "          /* Semantic button tokens */",
        f"          --ui-btn-save-bg: {brand};",
        f"          --ui-btn-save-hover: {brand_hover};",
        f"          --ui-btn-save-fg: {brand_contrast};",
        f"          --ui-btn-destruct-bg: {error_bg};",
        f"          --ui-btn-destruct-border: {error_border};",
        f"          --ui-btn-destruct-hover: {mix_hex('#ffffff', color('semantic-error'), 0.22)};",
        f"          --ui-btn-destruct-fg: {error_fg};",
        f"          --ui-btn-neutral-bg: {canvas};",
        f"          --ui-btn-neutral-border: {hairline};",
        f"          --ui-btn-neutral-hover: {surface_soft};",
        f"          --ui-btn-neutral-fg: {body};",
        f"          --ui-btn-affirm-bg: {canvas};",
        f"          --ui-btn-affirm-border: {hairline};",
        f"          --ui-btn-affirm-hover: {surface_soft};",
        f"          --ui-btn-affirm-fg: {ink};",
        "          /* Bucket accents — Próximas acciones */",
        f"          --ui-bucket-past: {bucket_past};",
        f"          --ui-bucket-today: {bucket_today};",
        f"          --ui-bucket-future: {bucket_future};",
        "          /* Radii */",
        f"          --ui-radius-md: {radius_md};",
        f"          --ui-radius-lg: {radius_lg};",
        "          /* Spacing */",
        f"          --ui-spacing-sm: {spacing_sm};",
        f"          --ui-spacing-md: {spacing_md};",
        f"          --ui-spacing-lg: {spacing_lg};",
        "          /* Semantic status (base) */",
        f"          --ui-semantic-success: {color('semantic-success')};",
        f"          --ui-semantic-warning: {color('semantic-warning')};",
        f"          --ui-semantic-error: {color('semantic-error')};",
        f"          --ui-semantic-info: {color('semantic-info')};",
        f"          --ui-semantic-purple: {color('semantic-purple')};",
        f"          --ui-kpi-success-bg: {success_bg};",
        f"          --ui-kpi-success-border: {success_border};",
        f"          --ui-kpi-warning-bg: {warning_bg};",
        f"          --ui-kpi-warning-border: {warning_border};",
        f"          --ui-kpi-danger-bg: {error_bg};",
        f"          --ui-kpi-danger-border: {error_border};",
        f"          --ui-kpi-info-bg: {info_bg};",
        f"          --ui-kpi-info-border: {info_border};",
        f"          --ui-kpi-purple-bg: {purple_bg};",
        f"          --ui-kpi-purple-border: {purple_border};",
        f"          --ui-kpi-neutral-bg: {neutral_bg};",
        f"          --ui-kpi-neutral-border: {neutral_border};",
        "          /* Estados propios de este CRM */",
        f"          --ui-supplier-confirmado: {color('supplier-confirmado', default='#4CAF78')};",
        f"          --ui-supplier-potencial: {color('supplier-potencial', default='#4A90D9')};",
        f"          --ui-supplier-descartado: {color('supplier-descartado', default='#B0B8C1')};",
        f"          --ui-price-winner: {color('price-winner', default='#2D6A4F')};",
        f"          --ui-price-expired: {color('price-expired', default='#F5A623')};",
        "          /* Movimiento — ver DESIGN-space.md § Movimiento */",
        f"          --ui-duration-instant: {motion('duration-instant')};",
        f"          --ui-duration-fast: {motion('duration-fast')};",
        f"          --ui-duration-base: {motion('duration-base')};",
        f"          --ui-duration-slow: {motion('duration-slow')};",
        f"          --ui-ease-out: {motion('ease-out')};",
        f"          --ui-ease-in-out: {motion('ease-in-out')};",
        f"          --ui-stagger-step: {motion('stagger-step')};",
        "        }",
    ]
    return "\n".join(lines)


def reset_cache() -> None:
    load_design_tokens.cache_clear()
