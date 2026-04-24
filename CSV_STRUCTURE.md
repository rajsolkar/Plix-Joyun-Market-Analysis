# CSV_STRUCTURE.md — Joyun Intel CSV Format (LOCKED)

Every daily CSV must have exactly these 10 columns, in this order:

| # | Column            | Type   | Notes |
|---|-------------------|--------|-------|
| 1 | Date              | string | YYYY-MM-DD (IST) |
| 2 | Brand             | string | Brand name |
| 3 | Product           | string | Specific product/SKU |
| 4 | Category          | string | Essence, Serum, Cleanser, Sunscreen, Mask, Toner, Eye Care, Body Care, Lip Care, Other |
| 5 | Key_Ingredients   | string | Comma-separated, lowercase |
| 6 | Price_INR         | number | Empty if unknown |
| 7 | Price_USD         | number | Empty if unknown |
| 8 | Threat_Level      | enum   | HIGH \| MEDIUM \| LOW \| ADJACENT |
| 9 | Direct_Competitor | enum   | YES \| NO |
| 10| Notes             | string | 1-2 sentences of context |

Filename pattern: `joyun_intel_YYYY-MM-DD.csv`
