#!/usr/bin/env python3
"""
Joyun Competitive Intelligence — Daily Research Runner
Supports BOTH Google Gemini (free tier) and Anthropic Claude (paid).

Switch providers with the LLM_PROVIDER env var:
  LLM_PROVIDER=gemini  (default)
  LLM_PROVIDER=claude

Pipeline:
  1. Call the configured LLM with web search to research skincare market
  2. Parse structured JSON output
  3. Write CSV (10 cols per CSV_STRUCTURE.md)
  4. Write Markdown report
  5. Render dashboard.html from template
"""

import os
import json
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DASHBOARD_PATH = ROOT / "dashboard.html"
TEMPLATE_PATH = ROOT / "dashboard-template.html"

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).strftime("%Y-%m-%d")

CSV_PATH = DATA_DIR / f"joyun_intel_{TODAY}.csv"
REPORT_PATH = DATA_DIR / f"joyun_report_{TODAY}.md"

PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()

# Model knobs — change these at the top, not buried in code.
GEMINI_MODEL = "gemini-2.5-flash"
CLAUDE_MODEL = "claude-sonnet-4-6"

# ─── The research prompt (provider-agnostic) ──────────────────────────────────
RESEARCH_PROMPT = f"""You are the daily competitive intelligence analyst for Joyun, an Indian skincare brand.

JOYUN'S CURRENT PRODUCTS:
- ROSE-03 Vegan Mucin Essence — INR 299 (~$3.60 USD)
- ROSE-04 PDRN Micro-Needle Serum — INR 950 (~$11.40 USD)

TODAY'S DATE: {TODAY}

YOUR JOB: Research the global skincare market today and find 10-15 actionable intelligence items.

RESEARCH SCOPE (cast a wide net — go beyond direct competitors):
1. DIRECT competitors: brands using Centella, PDRN, vegan mucin, snail mucin, rose extracts
2. EMERGING ingredients: mushrooms (tremella, reishi), postbiotics, adaptogens, peptides, exosomes,
   fermented actives, microbiome-targeting ingredients
3. FORMAT INNOVATIONS: toner pads, sheet masks, ampoules, sticks, in-shower treatments, overnight masks
4. CATEGORY GAPS for Joyun: cleansers, sunscreens, eye care, body care, lip care
5. POSITIONING TRENDS: skinimalism, fermented beauty, microbiome-first, "skin barrier" focus,
   K-beauty/J-beauty/C-beauty waves
6. ADJACENT competitors: Indian brands (Dot & Key, Minimalist, Plum, The Derma Co, Foxtale, etc.)
   AND global brands launching in India (Beauty of Joseon, COSRX, Anua, etc.)
7. Price moves, new launches, viral products, M&A, retail expansion

SEARCH STRATEGY:
- Search recent skincare news from the past 7 days
- Check K-beauty and J-beauty trend trackers
- Look at Indian skincare launches and DTC brand news

OUTPUT FORMAT (STRICT — CRITICAL):
Your final response must include a single ```json code block containing your findings.
Use this EXACT schema. All fields required (use null where unknown):

```json
{{
  "summary": "2-3 sentence executive summary",
  "alert": "ONE most urgent thing for Joyun today, or null if nothing urgent",
  "stats": {{
    "items_tracked": 12,
    "high_threat": 0,
    "medium_threat": 0,
    "low_threat": 0,
    "adjacent": 0
  }},
  "hot_ingredients": [
    {{"ingredient": "name", "trend": "what's happening", "joyun_relevance": "why Joyun should care"}}
  ],
  "competitor_activity": [
    {{"brand": "name", "activity": "what they did", "threat_level": "HIGH|MEDIUM|LOW", "implication": "for Joyun"}}
  ],
  "opportunities": [
    {{"opportunity": "the gap", "rationale": "why now", "suggested_action": "concrete next step"}}
  ],
  "where_joyun_can_shine": [
    "specific angle Joyun is uniquely positioned to win on"
  ],
  "items": [
    {{
      "brand": "Brand Name",
      "product": "Product Name",
      "category": "Essence|Serum|Cleanser|Sunscreen|Mask|Toner|Eye Care|Body Care|Lip Care|Other",
      "key_ingredients": "ingredient1, ingredient2",
      "price_inr": null,
      "price_usd": null,
      "threat_level": "HIGH|MEDIUM|LOW|ADJACENT",
      "direct_competitor": "YES|NO",
      "notes": "1-2 sentences of why this matters"
    }}
  ]
}}
```

CRITICAL RULES:
- Items count: 10-15
- threat_level: HIGH = directly competes with ROSE-03 or ROSE-04 at similar price; MEDIUM = same category, different positioning; LOW = same brand space but different product; ADJACENT = relevant trend signal
- Use REAL data from your searches — do not fabricate brands or prices
- If you only know one of price_inr / price_usd, convert: 1 USD ≈ 83.5 INR
- The ```json block must be the LAST thing in your response
- Make sure stats numbers actually match what's in the items array
"""


# ─── Provider implementations ─────────────────────────────────────────────────
def run_research_gemini() -> str:
    """Call Gemini 2.5 Flash with google_search grounding. Returns full text."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print(f"[{datetime.now().isoformat()}] Calling Gemini ({GEMINI_MODEL}) with google_search…")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=RESEARCH_PROMPT,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
        ),
    )
    return response.text or ""


def run_research_claude() -> str:
    """Call Claude with web_search tool. Returns full text."""
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    print(f"[{datetime.now().isoformat()}] Calling Claude ({CLAUDE_MODEL}) with web_search…")
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": RESEARCH_PROMPT}],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 8,
        }],
    )
    return "".join(b.text for b in response.content if b.type == "text")


# ─── Pipeline ────────────────────────────────────────────────────────────────
def run_research() -> dict:
    if PROVIDER == "gemini":
        full_text = run_research_gemini()
    elif PROVIDER == "claude":
        full_text = run_research_claude()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")

    # Try fenced ```json block first; fall back to last {…} blob if model omitted fences
    match = re.search(r"```json\s*(\{.*?\})\s*```", full_text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # fallback: grab the largest balanced JSON object in the response
        candidates = re.findall(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", full_text, re.DOTALL)
        candidates = [c for c in candidates if '"items"' in c and '"summary"' in c]
        if not candidates:
            raise ValueError(
                f"{PROVIDER} did not return parseable JSON. First 2000 chars:\n{full_text[:2000]}"
            )
        json_str = max(candidates, key=len)

    findings = json.loads(json_str)
    print(f"Got {len(findings.get('items', []))} items")

    narrative = full_text.split("```json")[0].strip()
    findings["_narrative"] = narrative
    return findings


def write_csv(findings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Date", "Brand", "Product", "Category", "Key_Ingredients",
            "Price_INR", "Price_USD", "Threat_Level", "Direct_Competitor", "Notes",
        ])
        for item in findings.get("items", []):
            w.writerow([
                TODAY,
                item.get("brand", ""),
                item.get("product", ""),
                item.get("category", ""),
                item.get("key_ingredients", ""),
                item.get("price_inr") or "",
                item.get("price_usd") or "",
                item.get("threat_level", ""),
                item.get("direct_competitor", ""),
                item.get("notes", ""),
            ])
    print(f"Wrote CSV: {CSV_PATH}")


def write_report(findings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Joyun Competitive Intelligence — {TODAY}",
        "",
        f"_Provider: {PROVIDER}_",
        "",
        "## Executive Summary",
        findings.get("summary", "_No summary._"),
        "",
    ]
    if findings.get("alert"):
        lines += ["## Urgent Alert", findings["alert"], ""]

    lines += ["## Hot Ingredients", ""]
    for ing in findings.get("hot_ingredients", []):
        lines.append(f"- **{ing.get('ingredient','')}** — {ing.get('trend','')} _(Joyun: {ing.get('joyun_relevance','')})_")
    lines.append("")

    lines += ["## Competitor Activity", ""]
    for c in findings.get("competitor_activity", []):
        lines.append(f"- **{c.get('brand','')}** [{c.get('threat_level','')}] — {c.get('activity','')} → {c.get('implication','')}")
    lines.append("")

    lines += ["## Opportunities", ""]
    for o in findings.get("opportunities", []):
        lines.append(f"- **{o.get('opportunity','')}** — {o.get('rationale','')} → _Action: {o.get('suggested_action','')}_")
    lines.append("")

    lines += ["## Where Joyun Can Shine", ""]
    for s in findings.get("where_joyun_can_shine", []):
        lines.append(f"- {s}")
    lines.append("")

    lines += ["## Research Narrative", "", findings.get("_narrative", "")]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report: {REPORT_PATH}")


def render_dashboard(findings: dict) -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def threat_class(level: str) -> str:
        return {"HIGH": "high", "MEDIUM": "medium", "LOW": "low", "ADJACENT": "adjacent"}.get(level, "low")

    ing_html = "\n".join(
        f'<div class="card"><h3>{i.get("ingredient","")}</h3>'
        f'<p class="trend">{i.get("trend","")}</p>'
        f'<p class="relevance"><strong>Joyun angle:</strong> {i.get("joyun_relevance","")}</p></div>'
        for i in findings.get("hot_ingredients", [])
    ) or "<p>No new ingredient signals today.</p>"

    comp_html = "\n".join(
        f'<div class="card threat-{threat_class(c.get("threat_level",""))}">'
        f'<h3>{c.get("brand","")} <span class="badge">{c.get("threat_level","")}</span></h3>'
        f'<p>{c.get("activity","")}</p><p class="implication">→ {c.get("implication","")}</p></div>'
        for c in findings.get("competitor_activity", [])
    ) or "<p>No competitor moves today.</p>"

    opp_html = "\n".join(
        f'<div class="card"><h3>{o.get("opportunity","")}</h3>'
        f'<p>{o.get("rationale","")}</p>'
        f'<p class="action"><strong>Action:</strong> {o.get("suggested_action","")}</p></div>'
        for o in findings.get("opportunities", [])
    ) or "<p>No new opportunities flagged.</p>"

    shine_html = "\n".join(
        f"<li>{s}</li>" for s in findings.get("where_joyun_can_shine", [])
    ) or "<li>Run more research to surface differentiators.</li>"

    stats = findings.get("stats", {}) or {}
    alert = findings.get("alert") or "No urgent alerts today."

    html = (
        template
        .replace("{{DATE}}", TODAY)
        .replace("{{SUMMARY}}", findings.get("summary", ""))
        .replace("{{ALERT}}", alert)
        .replace("{{ITEMS_TRACKED}}", str(stats.get("items_tracked", len(findings.get("items", [])))))
        .replace("{{HIGH_THREAT}}", str(stats.get("high_threat", 0)))
        .replace("{{MEDIUM_THREAT}}", str(stats.get("medium_threat", 0)))
        .replace("{{LOW_THREAT}}", str(stats.get("low_threat", 0)))
        .replace("{{ADJACENT}}", str(stats.get("adjacent", 0)))
        .replace("{{HOT_INGREDIENTS}}", ing_html)
        .replace("{{COMPETITOR_ACTIVITY}}", comp_html)
        .replace("{{OPPORTUNITIES}}", opp_html)
        .replace("{{WHERE_JOYUN_SHINES}}", shine_html)
        .replace("{{CSV_FILENAME}}", CSV_PATH.name)
        .replace("{{REPORT_FILENAME}}", REPORT_PATH.name)
    )

    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote dashboard: {DASHBOARD_PATH}")


def main() -> None:
    print(f"Provider: {PROVIDER}")
    findings = run_research()
    write_csv(findings)
    write_report(findings)
    render_dashboard(findings)

    (DATA_DIR / f"findings_{TODAY}.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Daily run complete.")


if __name__ == "__main__":
    main()
