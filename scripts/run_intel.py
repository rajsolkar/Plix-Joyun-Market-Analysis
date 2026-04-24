#!/usr/bin/env python3
"""
Joyun Competitive Intelligence — Daily Research Runner
Replaces Kimi with Claude API + web_search tool.

Pipeline:
  1. Call Claude API with web_search to research the global skincare market
  2. Parse Claude's structured output into CSV (10 cols per CSV_STRUCTURE.md)
  3. Write a Markdown report
  4. Render dashboard.html from template
"""

import os
import json
import csv
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

# ─── Configuration ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DASHBOARD_PATH = ROOT / "dashboard.html"
TEMPLATE_PATH = ROOT / "dashboard-template.html"

IST = timezone(timedelta(hours=5, minutes=30))
TODAY = datetime.now(IST).strftime("%Y-%m-%d")

CSV_PATH = DATA_DIR / f"joyun_intel_{TODAY}.csv"
REPORT_PATH = DATA_DIR / f"joyun_report_{TODAY}.md"

MODEL = "claude-opus-4-7"  # Best model for research; switch to claude-sonnet-4-6 for cost savings

# ─── The research prompt ──────────────────────────────────────────────────────
RESEARCH_PROMPT = f"""You are the daily competitive intelligence analyst for Joyun, an Indian skincare brand.

JOYUN'S CURRENT PRODUCTS:
- ROSE-03 Vegan Mucin Essence — ₹299 (~$3.60 USD)
- ROSE-04 PDRN Micro-Needle Serum — ₹950 (~$11.40 USD)

TODAY'S DATE: {TODAY}

YOUR JOB: Research the global skincare market today and find 15-25 actionable intelligence items.

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
- Find ingredient innovation reports

OUTPUT FORMAT (STRICTLY FOLLOW THIS):
After your research, output your findings inside a single ```json code block. Use this exact schema:

```json
{{
  "summary": "2-3 sentence executive summary of today's most important findings for Joyun",
  "alert": "ONE most urgent thing Joyun's team should know about today (or null if nothing urgent)",
  "stats": {{
    "items_tracked": <int>,
    "high_threat": <int>,
    "medium_threat": <int>,
    "low_threat": <int>,
    "adjacent": <int>
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
      "price_inr": <number or null>,
      "price_usd": <number or null>,
      "threat_level": "HIGH|MEDIUM|LOW|ADJACENT",
      "direct_competitor": "YES|NO",
      "notes": "1-2 sentences of why this matters"
    }}
  ]
}}
```

CRITICAL RULES:
- Items count must be 15-25
- threat_level reasoning: HIGH = directly competes with ROSE-03 or ROSE-04 at similar price; MEDIUM = same category, different positioning; LOW = same brand space but different product; ADJACENT = relevant trend signal
- Use real, current data from your searches — do NOT fabricate brands or prices
- Convert prices: 1 USD ≈ 83.5 INR (use this if you only know one)
- Output the JSON block AT THE END of your response, after your research narrative
"""


# ─── Main pipeline ────────────────────────────────────────────────────────────
def run_research() -> dict:
    """Call Claude API with web_search, return parsed JSON findings."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    print(f"[{datetime.now().isoformat()}] Calling Claude API with web_search…")
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": RESEARCH_PROMPT}],
        tools=[{
            "type": "web_search_20260209",  # latest version with dynamic filtering
            "name": "web_search",
            "max_uses": 15,
        }],
    )

    # Concatenate all text blocks from the response
    full_text = "".join(
        block.text for block in response.content if block.type == "text"
    )

    # Extract the JSON block
    match = re.search(r"```json\s*(\{.*?\})\s*```", full_text, re.DOTALL)
    if not match:
        raise ValueError(
            "Claude did not return a parseable JSON block. Full response:\n"
            + full_text[:2000]
        )

    findings = json.loads(match.group(1))
    print(f"[{datetime.now().isoformat()}] Got {len(findings.get('items', []))} items")

    # Stash the raw narrative for the markdown report
    narrative = full_text.split("```json")[0].strip()
    findings["_narrative"] = narrative
    return findings


def write_csv(findings: dict) -> None:
    """Write the 10-column CSV per CSV_STRUCTURE.md."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Date", "Brand", "Product", "Category", "Key_Ingredients",
            "Price_INR", "Price_USD", "Threat_Level", "Direct_Competitor", "Notes",
        ])
        for item in findings["items"]:
            w.writerow([
                TODAY,
                item.get("brand", ""),
                item.get("product", ""),
                item.get("category", ""),
                item.get("key_ingredients", ""),
                item.get("price_inr", "") or "",
                item.get("price_usd", "") or "",
                item.get("threat_level", ""),
                item.get("direct_competitor", ""),
                item.get("notes", ""),
            ])
    print(f"Wrote CSV: {CSV_PATH}")


def write_report(findings: dict) -> None:
    """Write the daily Markdown report."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Joyun Competitive Intelligence — {TODAY}",
        "",
        "## Executive Summary",
        findings.get("summary", "_No summary._"),
        "",
    ]
    if findings.get("alert"):
        lines += ["## ⚠️ Urgent Alert", findings["alert"], ""]

    lines += ["## Hot Ingredients", ""]
    for ing in findings.get("hot_ingredients", []):
        lines.append(f"- **{ing['ingredient']}** — {ing['trend']} _(Joyun: {ing['joyun_relevance']})_")
    lines.append("")

    lines += ["## Competitor Activity", ""]
    for c in findings.get("competitor_activity", []):
        lines.append(f"- **{c['brand']}** [{c['threat_level']}] — {c['activity']} → {c['implication']}")
    lines.append("")

    lines += ["## Opportunities", ""]
    for o in findings.get("opportunities", []):
        lines.append(f"- **{o['opportunity']}** — {o['rationale']} → _Action: {o['suggested_action']}_")
    lines.append("")

    lines += ["## Where Joyun Can Shine", ""]
    for s in findings.get("where_joyun_can_shine", []):
        lines.append(f"- {s}")
    lines.append("")

    lines += ["## Research Narrative", "", findings.get("_narrative", "")]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report: {REPORT_PATH}")


def render_dashboard(findings: dict) -> None:
    """Fill the HTML template with today's findings."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    def threat_class(level: str) -> str:
        return {"HIGH": "high", "MEDIUM": "medium", "LOW": "low", "ADJACENT": "adjacent"}.get(level, "low")

    # Hot ingredients HTML
    ing_html = "\n".join(
        f'<div class="card"><h3>{i["ingredient"]}</h3>'
        f'<p class="trend">{i["trend"]}</p>'
        f'<p class="relevance"><strong>Joyun angle:</strong> {i["joyun_relevance"]}</p></div>'
        for i in findings.get("hot_ingredients", [])
    ) or "<p>No new ingredient signals today.</p>"

    # Competitor activity HTML
    comp_html = "\n".join(
        f'<div class="card threat-{threat_class(c["threat_level"])}">'
        f'<h3>{c["brand"]} <span class="badge">{c["threat_level"]}</span></h3>'
        f'<p>{c["activity"]}</p><p class="implication">→ {c["implication"]}</p></div>'
        for c in findings.get("competitor_activity", [])
    ) or "<p>No competitor moves today.</p>"

    # Opportunities HTML
    opp_html = "\n".join(
        f'<div class="card"><h3>{o["opportunity"]}</h3>'
        f'<p>{o["rationale"]}</p>'
        f'<p class="action"><strong>Action:</strong> {o["suggested_action"]}</p></div>'
        for o in findings.get("opportunities", [])
    ) or "<p>No new opportunities flagged.</p>"

    # Where Joyun shines HTML
    shine_html = "\n".join(
        f"<li>{s}</li>" for s in findings.get("where_joyun_can_shine", [])
    ) or "<li>Run more research to surface differentiators.</li>"

    stats = findings.get("stats", {})
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
    findings = run_research()
    write_csv(findings)
    write_report(findings)
    render_dashboard(findings)

    # Save findings JSON too — useful for the telegram script and debugging
    (DATA_DIR / f"findings_{TODAY}.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("✅ Daily run complete.")


if __name__ == "__main__":
    main()
