"""Title / description / comment ke liye chhota template engine.

Supported variables:
    {n}         -> upload number (1, 2, 3 ...)
    {nn}        -> zero padded upload number (01, 02 ...)
    {total}     -> campaign ka total uploads
    {date}      -> 17-08-2026
    {time}      -> 14:30
    {datetime}  -> 17-08-2026 14:30
    {day}       -> Monday
    {campaign}  -> campaign ka naam
    {rand}      -> 4 digit random number
    {emoji}     -> random emoji

Spintax bhi chalta hai taaki har upload ka title/comment thoda alag rahe:
    {Nice|Great|Superb} video -> "Great video"
Nested spintax supported hai.
"""

import random
import re
from datetime import timezone

EMOJIS = ["🔥", "✨", "🚀", "💯", "🎬", "😍", "👌", "⚡", "🌟", "🎯"]

_SPIN_RE = re.compile(r"\{([^{}]*\|[^{}]*)\}")


def build_context(seq, total, campaign_name, when, tz=timezone.utc):
    local = when.astimezone(tz)
    return {
        "n": str(seq),
        "nn": f"{seq:02d}",
        "total": str(total),
        "date": local.strftime("%d-%m-%Y"),
        "time": local.strftime("%H:%M"),
        "datetime": local.strftime("%d-%m-%Y %H:%M"),
        "day": local.strftime("%A"),
        "campaign": campaign_name or "",
        "rand": str(random.randint(1000, 9999)),
        "emoji": random.choice(EMOJIS),
    }


def _expand_spintax(text, rng):
    # Andar se bahar ki taraf resolve karo, isliye loop.
    for _ in range(20):
        match = _SPIN_RE.search(text)
        if not match:
            break
        choice = rng.choice(match.group(1).split("|"))
        text = text[: match.start()] + choice + text[match.end() :]
    return text


def render(template, context, seed=None):
    """Variables replace karo, phir spintax resolve karo."""
    if not template:
        return ""
    out = template
    for key, value in context.items():
        out = out.replace("{" + key + "}", value)
    rng = random.Random(seed) if seed is not None else random
    return _expand_spintax(out, rng).strip()


def preview(template, campaign_name="Demo Campaign", total=24, count=3):
    """Dashboard ke liye pehle kuch outputs ka preview."""
    from db import utcnow

    now = utcnow()
    return [
        render(template, build_context(i + 1, total, campaign_name, now))
        for i in range(count)
    ]
