import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")

def safe_write(path: Path, data: str, force: bool = False) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists. Use --force to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")

def to_markdown(pkg: Dict[str, Any]) -> str:
    parts = []
    parts.append(f"# {pkg.get('title', 'Untitled')}\n")
    
    meta = pkg.get("meta", {})
    meta_lines = []
    for k in ["genre", "mood", "topic", "key", "tempo_bpm", "language", "structure"]:
        v = meta.get(k)
        if v:
            label = k.replace("_", " ").title()
            meta_lines.append(f"- **{label}:** {v}")
    if meta_lines:
        parts.append("## Details\n" + "\n".join(meta_lines) + "\n")
    
    if pkg.get("logline"):
        parts.append("## Logline\n" + pkg["logline"] + "\n")
    
    ideas = pkg.get("musical_ideas")
    if ideas:
        parts.append("## Musical Ideas\n")
        if ideas.get("chord_progression"):
            parts.append(f"**Chord Progression (Key {meta.get('key','?')}):** {ideas['chord_progression']}\n")
        if ideas.get("strumming_pattern"):
            parts.append(f"**Strumming/Feel:** {ideas['strumming_pattern']}\n")
        if ideas.get("melodic_hint"):
            parts.append(f"**Melodic Hint:** {ideas['melodic_hint']}\n")
    
    sections = pkg.get("lyrics", {})
    if sections:
        parts.append("## Lyrics\n")
        for name, text in sections.items():
            parts.append(f"### {name.title()}\n{text}\n")
    
    if pkg.get("production_notes"):
        parts.append("## Production Notes\n" + pkg["production_notes"] + "\n")
    return "\n".join(parts)


def build_prompt(args: argparse.Namespace) -> str:
    return f'''You are an award-winning songwriter and music theorist.
Write a cohesive *song package* based on the brief. The output **must be valid JSON** matching the schema below.

Brief:
- Genre: {args.genre or "any"}
- Mood: {args.mood or "any"}
- Topic: {args.topic or "surprise me"}
- Language: {args.language or "English"}
- Key: {args.key or "best fit"}
- Tempo (BPM): {args.tempo or "best fit"}
- Structure: {args.structure or "verse, chorus, verse, chorus, bridge, chorus"}
- Rhyme scheme: {args.rhyme or "flexible"}
- Syllable count (target): {args.syllables or "flexible"}

Rules:
- Keep it singable. Natural phrasing. Avoid forced rhymes.
- Ensure the chord progression matches the specified (or chosen) key.
- If chords imply modal interchange or borrowed chords, keep it tasteful.
- Write lyrics section-by-section following the structure. Avoid placeholders.
- Provide melodic guidance as a simple contour or solfege phrase (e.g., "mi fa so la so").
- JSON only. No backticks, no commentary.
- - Only return chords in **Music21-compatible notation**:
    - Minor: use 'm' (e.g., Dm, Em7)
    - Major triads: just the note letter (e.g., C, G)
    - Seventh chords: use 7 (e.g., C7, G7, Em7)
    - Sus, diminished, augmented chords are allowed as: sus2, sus4, dim, aug
    - Avoid words like 'min', 'maj', or any modifiers Music21 cannot parse
- Do NOT include section labels or commentary in chord names.
- Use | to separate chords in the progression.

JSON schema (keys and types must match exactly):
{{
  "title": "string",
  "logline": "string",
  "meta": {{
    "genre": "string",
    "mood": "string",
    "topic": "string",
    "language": "string",
    "key": "string",
    "tempo_bpm": "integer",
    "structure": "string"
  }},
  "lyrics": {{
    "intro": "string (optional, can be empty)",
    "verse_1": "string",
    "pre_chorus_1": "string (optional, can be empty)",
    "chorus": "string",
    "verse_2": "string (optional, can be empty)",
    "pre_chorus_2": "string (optional, can be empty)",
    "bridge": "string (optional, can be empty)",
    "outro": "string (optional, can be empty)"
  }},
  "musical_ideas": {{
    "chord_progression": "string (e.g., C | Am | F | G)",
    "strumming_pattern": "string (e.g., D D U U D U, or \"4 on the floor\")",
    "melodic_hint": "string (solfege or contour like ^1-^3-^4-^5)"
  }},
  "production_notes": "string"
}}
'''

def call_openai(prompt: str, model: str) -> str:
    client = OpenAI()
    resp = client.responses.create(
        model=model,
        input=prompt,
    )
    # The Python SDK provides a convenience accessor:
    return getattr(resp, "output_text", None) or json.dumps(resp.to_dict(), ensure_ascii=False)

def generate_package(args: argparse.Namespace) -> Dict[str, Any]:
    # Compose the prompt and call the model
    prompt = build_prompt(args)
    text = call_openai(
        prompt=prompt,
        model=args.model,
    )
    # Parse JSON (with one-pass cleanup if needed)
    def try_parse(s: str) -> Dict[str, Any]:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # Fallback: attempt to trim any leading/trailing noise
            start = s.find("{")
            end = s.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(s[start:end+1])
            raise
    
    pkg = try_parse(text)
    # Fill meta defaults if missing
    pkg.setdefault("meta", {})
    m = pkg["meta"]
    m.setdefault("genre", args.genre or "unspecified")
    m.setdefault("mood", args.mood or "unspecified")
    m.setdefault("topic", args.topic or "unspecified")
    m.setdefault("language", args.language or "English")
    m.setdefault("key", args.key or "TBD")
    m.setdefault("tempo_bpm", args.tempo or 0)
    m.setdefault("structure", args.structure or "V-C-V-C-B-C")
    return pkg

def main():
    load_dotenv()  # loads OPENAI_API_KEY if present
    parser = argparse.ArgumentParser(description="Generate a complete song package with OpenAI.")
    parser.add_argument("--genre", type=str, help="e.g. pop, folk, rock, r&b")
    parser.add_argument("--mood", type=str, help="e.g. melancholic, euphoric, bittersweet")
    parser.add_argument("--topic", type=str, help="song topic or theme")
    parser.add_argument("--key", type=str, help="musical key, e.g. C, Gm, Eb")
    parser.add_argument("--tempo", type=int, help="BPM, e.g. 92")
    parser.add_argument("--language", type=str, default="English", help="lyrics language")
    parser.add_argument("--structure", type=str, help="e.g. verse, chorus, verse, chorus, bridge, chorus")
    parser.add_argument("--rhyme", type=str, help="e.g. ABAB, AABB, or flexible")
    parser.add_argument("--syllables", type=str, help="target syllables per line or 'flexible'")
    parser.add_argument("--model", type=str, default=os.getenv("OPENAI_MODEL", "gpt-5-mini"), help="OpenAI model name")
    parser.add_argument("--outdir", type=Path, default=Path("songs"), help="output directory")
    parser.add_argument("--basename", type=str, help="base file name without extension")
    parser.add_argument("--force", action="store_true", help="overwrite outputs if they exist")
    args = parser.parse_args()

    # Run generation
    pkg = generate_package(args)
    
    # Prepare filenames
    base = args.basename or f"{pkg.get('title','untitled').strip().replace(' ', '_')}_{timestamp()}"
    json_path = args.outdir / f"{base}.json"
    md_path = args.outdir / f"{base}.md"
    
    # Save files
    safe_write(json_path, json.dumps(pkg, ensure_ascii=False, indent=2), force=args.force)
    safe_write(md_path, to_markdown(pkg), force=args.force)
    
    print(f"✅ Saved:\n- {json_path}\n- {md_path}")
    print("\nTip: paste the chord progression into your DAW, and use the 'melodic_hint' as a guide for topline sketches.")

if __name__ == "__main__":
    main()
