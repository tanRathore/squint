EMOJI = {
    "likely_synthetic": "🔴",
    "leaning_synthetic": "🟠",
    "unclear": "⚪",
    "leaning_human": "🟢",
    "no_ai_signals": "🟢",
    "verified_capture": "📷",
}


def format_reply(v, hint=False):
    lines = [f"{EMOJI.get(v.tier, '⚪')} {v.headline}"]
    if v.say:
        lines.append(v.say)
    ev = [e for e in v.evidence if e and e not in v.say][:3]
    if ev:
        lines.append("")
        lines.extend(f"• {e}" for e in ev)
    if v.factchecks:
        fc = v.factchecks[0]
        if fc.get("url"):
            lines.append("")
            lines.append(f"{fc.get('publisher', 'fact check')}: {fc['url']}")
    if hint:
        lines.append("")
        lines.append("reply 'wrong' if we got this one wrong")
    return "\n".join(lines)
