from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _money(x: float) -> str:
    return f"$ {x:,.0f}".replace("$ ", "$")


def render_screen(forecast: dict[str, Any], benchmark: dict[str, Any] | None, output: Path) -> None:
    f = forecast["forecast"]
    ranges = sorted(f.get("range_probabilities", []), key=lambda x: x["probability"], reverse=True)
    hits = f.get("hit_probabilities", [])
    feature = forecast.get("features", {})
    context = forecast.get("context", {})
    decision = forecast.get("decision", "UNKNOWN")

    rows = "".join(
        f"<tr><td>{html.escape(x['label'])}</td><td>{x['probability']*100:.1f}%</td></tr>" for x in ranges[:5]
    )
    hit_rows = "".join(
        f"<tr><td>{html.escape(x['direction'])} {_money(x['target'])}</td><td>{x['probability']*100:.1f}%</td></tr>" for x in hits[:8]
    )

    bench_rows = ""
    if benchmark:
        by_bounds = {(x["lower"], x["upper"]): x for x in benchmark.get("ranges", [])}
        parts = []
        for x in ranges[:5]:
            b = by_bounds.get((x["lower"], x["upper"]), {})
            p = b.get("polymarket_midpoint")
            delta = None if p is None else x["probability"] - p
            parts.append(
                "<tr>"
                f"<td>{html.escape(x['label'])}</td>"
                f"<td>{x['probability']*100:.1f}%</td>"
                f"<td>{'—' if p is None else f'{p*100:.1f}%'}</td>"
                f"<td>{'—' if delta is None else f'{delta*100:+.1f} pp'}</td>"
                "</tr>"
            )
        bench_rows = "".join(parts)

    css = """
    body{font-family:Inter,system-ui,sans-serif;background:#0b0f14;color:#e8eef7;margin:0;padding:28px}
    .wrap{max-width:980px;margin:auto}.card{background:#121923;border:1px solid #253040;border-radius:16px;padding:20px;margin:14px 0}
    h1,h2{margin:.2em 0}.muted{color:#90a0b5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
    .metric{background:#0e151e;border-radius:12px;padding:14px}.big{font-size:28px;font-weight:700}table{width:100%;border-collapse:collapse}
    td,th{padding:10px;border-bottom:1px solid #253040;text-align:left}.pill{display:inline-block;padding:5px 10px;border-radius:999px;background:#1e2938}
    """
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><title>Daily Quant Screen</title><style>{css}</style></head>
    <body><div class='wrap'>
    <h1>Daily Quant Screen — BTC</h1><div class='muted'>Locked {html.escape(forecast['locked_at'])}</div>
    <div class='grid'>
      <div class='metric'><div class='muted'>Current</div><div class='big'>{_money(feature.get('current_price',0))}</div></div>
      <div class='metric'><div class='muted'>Confidence</div><div class='big'>{f.get('confidence','—')}</div></div>
      <div class='metric'><div class='muted'>Event risk</div><div class='big'>{html.escape(str(context.get('event_risk','UNKNOWN')))}</div></div>
      <div class='metric'><div class='muted'>Decision</div><div class='big'>{html.escape(decision)}</div></div>
    </div>
    <div class='card'><h2>Range model</h2><table><thead><tr><th>Bracket</th><th>Quant probability</th></tr></thead><tbody>{rows}</tbody></table></div>
    <div class='card'><h2>Hit model</h2><table><thead><tr><th>Level</th><th>Probability</th></tr></thead><tbody>{hit_rows or '<tr><td colspan=2>No hit markets discovered</td></tr>'}</tbody></table></div>
    <div class='card'><h2>Market benchmark — read after forecast lock</h2><table><thead><tr><th>Bracket</th><th>Quant</th><th>Polymarket</th><th>Δ</th></tr></thead><tbody>{bench_rows or '<tr><td colspan=4>Benchmark unavailable</td></tr>'}</tbody></table></div>
    <div class='card'><h2>Regime</h2><span class='pill'>{html.escape(str(feature.get('regime','UNKNOWN')))}</span><p class='muted'>{html.escape(str(context.get('summary','')))}</p></div>
    </div></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(doc, encoding="utf-8")
