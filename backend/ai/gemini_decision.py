"""
ai/gemini_decision.py
======================
Intégration Google AI Studio (Gemini) pour la décision globale.
Construit un prompt structuré avec toutes les analyses PhysioAI
et retourne un rapport de décision intelligent.

API : https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent
"""

from __future__ import annotations
import json, httpx, re
from typing import List, Dict, Any, Optional
from loguru import logger


GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-lite:generateContent"
)


# ─────────────────────────────────────────────────────────────────────────────
# Construction du prompt
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(
    x: List[float],
    y: List[float],
    context: str,
    regression_result: Optional[Dict],
    physical_result: Optional[Dict],
    ai_advisor_result: Optional[Dict],
    language: str,
) -> str:

    n = len(x)
    x_sample = x[:8]
    y_sample = y[:8]

    # Résumé régression
    reg_summary = "Non réalisée."
    if regression_result:
        m = regression_result.get("metrics") or {}
        eq = regression_result.get("equation", "")
        bm = regression_result.get("best_model", regression_result.get("model", ""))
        r2 = m.get("r2", "?")
        reg_summary = f"Modèle : {bm} | Équation : {eq} | R²={r2}"

    # Résumé physique
    phys_summary = "Non réalisée."
    if physical_result:
        pm = physical_result.get("model", "")
        eq = physical_result.get("equation", "")
        r2 = physical_result.get("r2", "")
        params = physical_result.get("params", {})
        phys_summary = (f"Modèle : {pm} | {eq} | "
                        f"Paramètres : {json.dumps(params)} "
                        + (f"| R²={r2}" if r2 else ""))

    # Résumé Advisor
    adv_summary = "Non réalisé."
    if ai_advisor_result:
        s = ai_advisor_result.get("summary", {})
        rec = ai_advisor_result.get("recommendations", {})
        primary = rec.get("primary_recommendation", {}) or {}
        adv_summary = (
            f"Tendance : {s.get('trend','?')} | "
            f"Complexité : {s.get('complexity','?')} | "
            f"Bruit : {s.get('noise','?')} | "
            f"Recommandation principale : {primary.get('model','?')} "
            f"({primary.get('confidence','?')} confiance) — {primary.get('reason','')}"
        )
        warnings = rec.get("warnings", [])
        if warnings:
            adv_summary += f" | Alertes : {'; '.join(warnings)}"

    if language == "fr":
        prompt = f"""Tu es un expert en génie des procédés, modélisation physico-chimique et intelligence artificielle.

## Contexte métier
{context if context else "Données expérimentales issues d'un processus industriel ou de laboratoire."}

## Données analysées
- Nombre de points : {n}
- Échantillon x : {x_sample}
- Échantillon y : {y_sample}
- Plage x : [{min(x):.4f} → {max(x):.4f}]
- Plage y : [{min(y):.4f} → {max(y):.4f}]

## Résultats des analyses PhysioAI Lab

### Régression
{reg_summary}

### Modèle physique
{phys_summary}

### Conseiller IA (analyse automatique)
{adv_summary}

## Ta mission
Produis un rapport de **décision globale structuré** en JSON strictement valide (sans backticks, sans texte avant/après) avec exactement ce format :

{{
  "decision_globale": {{
    "verdict": "string court — ex: Cinétique ordre 1 confirmée avec excellente qualité",
    "confiance": "haute|moyenne|faible",
    "score_qualite_donnees": 0-100
  }},
  "interpretation_physique": {{
    "phenomene_detecte": "string",
    "mecanisme": "string",
    "parametres_cles": ["string", "string"],
    "signification_physique": "string"
  }},
  "validation_croisee": {{
    "coherence_regression_physique": "string",
    "points_forts": ["string"],
    "points_attention": ["string"]
  }},
  "recommandations_prioritaires": [
    {{
      "priorite": 1,
      "action": "string",
      "justification": "string",
      "impact_attendu": "string"
    }}
  ],
  "prochaines_etapes": {{
    "court_terme": ["string"],
    "moyen_terme": ["string"],
    "experiences_suggerees": ["string"]
  }},
  "risques": [
    {{"risque": "string", "probabilite": "haute|moyenne|faible", "mitigation": "string"}}
  ],
  "resume_executif": "string — 2-3 phrases pour un décideur non-technique"
}}"""
    else:  # english
        prompt = f"""You are an expert in process engineering, physicochemical modeling and AI.

## Business context
{context if context else "Experimental data from an industrial or laboratory process."}

## Dataset
- Points: {n}
- x sample: {x_sample}
- y sample: {y_sample}
- x range: [{min(x):.4f} → {max(x):.4f}]
- y range: [{min(y):.4f} → {max(y):.4f}]

## PhysioAI Lab analysis results

### Regression: {reg_summary}
### Physical model: {phys_summary}
### AI Advisor: {adv_summary}

## Task
Return a **global decision report** as strictly valid JSON (no backticks, no surrounding text):

{{
  "global_decision": {{
    "verdict": "short string",
    "confidence": "high|medium|low",
    "data_quality_score": 0-100
  }},
  "physical_interpretation": {{
    "detected_phenomenon": "string",
    "mechanism": "string",
    "key_parameters": ["string"],
    "physical_meaning": "string"
  }},
  "cross_validation": {{
    "regression_vs_physical_coherence": "string",
    "strengths": ["string"],
    "concerns": ["string"]
  }},
  "priority_recommendations": [
    {{"priority": 1, "action": "string", "justification": "string", "expected_impact": "string"}}
  ],
  "next_steps": {{
    "short_term": ["string"],
    "medium_term": ["string"],
    "suggested_experiments": ["string"]
  }},
  "risks": [
    {{"risk": "string", "probability": "high|medium|low", "mitigation": "string"}}
  ],
  "executive_summary": "2-3 sentences for a non-technical decision maker"
}}"""

    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# Appel Gemini API
# ─────────────────────────────────────────────────────────────────────────────

async def call_gemini(prompt: str, api_key: str) -> str:
    """Appelle l'API Gemini et retourne le texte brut de la réponse."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.2,
            "topP":            0.8,
            "maxOutputTokens": 2048,
        },
    }
    headers = {"Content-Type": "application/json"}
    url = f"{GEMINI_URL}?key={api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Gemini API error {resp.status_code}: {resp.text[:300]}"
        )
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ─────────────────────────────────────────────────────────────────────────────
# Parser JSON de la réponse Gemini
# ─────────────────────────────────────────────────────────────────────────────

def _parse_gemini_json(raw: str) -> Dict[str, Any]:
    """Extrait et parse le JSON de la réponse Gemini."""
    # Nettoyage des backticks markdown éventuels
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    # Tenter le parse direct
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Extraire le premier objet JSON trouvé
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Impossible de parser la réponse Gemini : {raw[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────

async def global_decision(
    x:               List[float],
    y:               List[float],
    gemini_api_key:  str,
    context:         str = "",
    regression_result:  Optional[Dict] = None,
    physical_result:    Optional[Dict] = None,
    ai_advisor_result:  Optional[Dict] = None,
    language:        str = "fr",
) -> Dict[str, Any]:
    """
    Orchestre l'appel Gemini avec toutes les analyses PhysioAI
    et retourne le rapport de décision structuré.
    """
    logger.info(f"global_decision — Gemini API — {len(x)} points — lang={language}")

    prompt   = _build_prompt(x, y, context, regression_result,
                              physical_result, ai_advisor_result, language)
    raw_resp = await call_gemini(prompt, gemini_api_key)
    logger.debug(f"Gemini raw response (200 chars): {raw_resp[:200]}")

    parsed   = _parse_gemini_json(raw_resp)

    return {
        "status":   "success",
        "language": language,
        "model":    "gemini-2.0-flash",
        "report":   parsed,
        "raw_response": raw_resp,   # Pour debug — peut être retiré en prod
    }
