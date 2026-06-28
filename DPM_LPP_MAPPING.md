# DPM 2025 → LPP Finder field mapping (verified)

Verified against DPM 2025 Vol I (rules) and Vol II (forms). Used by the Archive / LPP Finder
so a search result is procurement-file-ready, not raw tender data. Forms are *indicative*
(DPMF 5, Note b); the export is a drafting aid — the indenter/IFA completes escalation/ERV and vets.

## Archive record schema — DPM Vol I §5.35.1 ("Database on Costs & Prices")
The manual requires Service HQs to keep, per past contract: item, essential specification(s),
unit rate, quantity, total value, mode of tendering, no. of tenders received, no. considered
acceptable, reasons unacceptable, un-negotiated L1 rate, contracted rate, delivery schedule,
delivery status. The archive models this, marked by source:

| §5.35.1 field | Source |
|---|---|
| item / nomenclature | auto — tender title |
| mode of tendering | auto — tender type (Open/Limited/Single/PAC/RC) |
| quantity, total/estimated value | auto/partial — tender detail page |
| awarded/contracted rate, un-negotiated L1, no. of bidders | defproc **Award-of-Contract** page *where published*; else from the buying unit |
| essential specification(s) | in the RFP/tender PDF (gated) → link to the defproc page |
| delivery schedule / status, reasons unacceptable | not published → from the buying unit |

## Result → SoC export — DPM Vol II DPMF 5 / DPMF 7
A search hit pre-fills:
- **DPMF 5 Ser 7 "Details of the Last Purchase"** — (a) similar item + quantity & date; (b) recurring
  period; (c) mode of tendering of last purchase; (d) source of last purchase; (e) other (tender ref + defproc link).
- **DPMF 5 Ser 6(a) Last Purchase Price** — "Year, Escalation Factor and its basis, source, quantity".
- **DPMF 7 (Estimated Quantity & Cost)** — per-unit cost basis = "per unit LPP, its vintage and the
  escalation factor (if applied)".

## Per-result reasonableness caveats — DPM Vol I §5.33.4
- (a) LPP > 3 years' vintage is not a clean scale — escalate (auto-flagged from the award FY).
- (b) Confirm same magnitude & scope of supply.
- (c) Account for basket price / bulk discount.
- (d) Consider Price-Variation-Clause final cost paid.
- (e) Confirm current production vs ex-stock supply.

## Optional escalation / ERV helper — DPM Vol I §5.32.2
- (c) Escalation via price indices (WPI/CPI/LME, etc.) — case-specific.
- (d) Delivery-period method: fix Price Level, escalate yearly from LPP FY (month-wise); e.g. LPP
  FY 2018-19 → escalate FY 2019-20 up to delivery FY 2024-25.
- (i) ERV: for bought-out-abroad / import-content items, add Exchange Rate Variation since last
  purchase. Helper output is **indicative**; indenter sets the factor.

## Category list (for tagging) — DPMF 5 Ser 2
Ordnance, Medical, IT, Engineering, MT, Electrical, Electronic, Clothing, Aviation, General, FOL,
Machinery, Spares, Communications, Navigational, Provisions, Weapons, Armament, Ammunition,
Repairs, Services, and others.
