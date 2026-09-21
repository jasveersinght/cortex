# JA Assure Compliance Rubric

This file is read by the compliance gate and injected into each lens's prompt.
Keep it simple and editable — no code changes needed to update rules.

---

## 1. CLAIMS LENS
Checks for prohibited or absolute language that insurance marketing cannot legally make.

Flag content that:
- Promises guaranteed payouts ("guaranteed claim approval", "100% covered", "always paid out")
- Implies zero risk or zero exclusions ("no exclusions ever", "covers everything")
- Uses absolute time promises without basis ("instant payout", "claims approved same day" unless contractually true)
- Omits required disclaimers when discussing coverage limits or premiums

Score 100 = no issues. Score drops sharply (by 30-50) for each absolute/guaranteed claim found.

---

## 2. REGULATORY LENS
Checks region-specific insurance advertising rules. Region is passed in per asset.

- **SG (Singapore)**: MAS guidelines — cannot claim guaranteed returns/payouts; must not misrepresent policy terms; promotional content aimed at retail customers must be fair, clear, not misleading.
- **MY (Malaysia)**: Bank Negara Malaysia rules — same misleading-claims restriction; no aggressive/high-pressure sales language.
- **HK (Hong Kong)**: Insurance Authority rules — must not imply insurer/product is officially endorsed by a government body.
- **ID (Indonesia)**: OJK rules — no misleading claims about premium/returns; must be in accordance with actual policy wording.
- **TH (Thailand)**: OIC rules — no exaggerated benefit claims; must not compare against competitors by name in a disparaging way.

Score 100 = fully compliant with the asset's stated region. Score drops for each rule violated.

---

## 3. BRAND LENS
Checks tone matches the brand voice.

- **Jade** (jewellers block insurance): premium, trust-forward, understated luxury tone. No slang, no excessive exclamation marks.
- **Jaguar Transit** (high-value goods transit): confident, operational, logistics-savvy tone. Speaks to B2B operators.
- **DoctorShield** (medical indemnity): professional, reassuring, precise. Never casual or "salesy" — doctors are the audience.

Score 100 = tone fully matches brand. Score drops for generic/off-brand tone, wrong formality level, or wrong audience framing.

---

## 4. ACCURACY LENS
Checks the asset's claims against actual policy wording (retrieved from policy docs / knowledge base).

Flag content that:
- States a coverage detail not found in or contradicted by the actual policy document
- Cites a premium, limit, or number that doesn't match source docs
- References a feature/benefit the product doesn't actually have

Score 100 = every specific claim traceable to source docs. Score drops heavily for any fabricated or contradicted detail (this is the highest-risk lens — factual/legal exposure).

---

## SCORING NOTES (used by aggregator.py)
- Each lens returns: score (0-100), flagged_phrases (list), reason (short string)
- Final confidence score = weighted average, but **Accuracy and Regulatory are weighted higher** since factual/legal risk matters most
- Weights: Claims 20%, Regulatory 30%, Brand 15%, Accuracy 35%