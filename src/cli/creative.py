"""Creative anti-degeneracy nudges for actual play turns.

These are intentionally light. Verse phrases are not persisted; they are
deterministic per turn so rerenders are stable. Tarot influences are persisted
by the caller in Postgres and exposed through `glass tarot`.
"""

from __future__ import annotations

import hashlib


NON_PLAY_MODES = {
    "none",
    "wrap",
    "worldbuilding",
    "campaign-bootstrap",
    "campaign-planning",
    "character-creation",
    "prelude",
    "intermission",
    "arc-creation",
    "scene-prep",
}


VERSE_PHRASES = [
    {
        "phrase": "a still small voice",
        "work": "King James Bible",
        "ref": "1 Kings 19:12",
    },
    {
        "phrase": "wheels within wheels",
        "work": "King James Bible",
        "ref": "Ezekiel 1:16",
    },
    {
        "phrase": "a cloud no bigger than a hand",
        "work": "King James Bible",
        "ref": "1 Kings 18:44",
    },
    {
        "phrase": "deep calleth unto deep",
        "work": "King James Bible",
        "ref": "Psalm 42:7",
    },
    {
        "phrase": "the sound of a going",
        "work": "King James Bible",
        "ref": "2 Samuel 5:24",
    },
    {
        "phrase": "this rough magic",
        "work": "The Tempest",
        "ref": "Act 5, Scene 1",
    },
    {
        "phrase": "the readiness is all",
        "work": "Hamlet",
        "ref": "Act 5, Scene 2",
    },
    {
        "phrase": "brave new world",
        "work": "The Tempest",
        "ref": "Act 5, Scene 1",
    },
    {
        "phrase": "lend me your ears",
        "work": "Julius Caesar",
        "ref": "Act 3, Scene 2",
    },
    {
        "phrase": "the wheel is come full circle",
        "work": "King Lear",
        "ref": "Act 5, Scene 3",
    },
    {
        "phrase": "return is the movement of the Tao",
        "work": "Tao Te Ching",
        "ref": "James Legge, ch. 40",
    },
    {
        "phrase": "the valley spirit dies not",
        "work": "Tao Te Ching",
        "ref": "James Legge, ch. 6",
    },
    {
        "phrase": "he who knows does not speak",
        "work": "Tao Te Ching",
        "ref": "James Legge, ch. 56",
    },
    {
        "phrase": "the soft overcomes the hard",
        "work": "Tao Te Ching",
        "ref": "James Legge, ch. 43",
    },
    {
        "phrase": "the uncarved block",
        "work": "Tao Te Ching",
        "ref": "James Legge, ch. 15",
    },
    {
        "phrase": "the cautious seldom err",
        "work": "Analects",
        "ref": "James Legge, Book IV",
    },
    {
        "phrase": "not to mend the fault is to err",
        "work": "Analects",
        "ref": "James Legge, Book XV",
    },
    {
        "phrase": "learning without thought is labor lost",
        "work": "Analects",
        "ref": "James Legge, Book II",
    },
    {
        "phrase": "the superior man is modest in speech",
        "work": "Analects",
        "ref": "James Legge, Book XIV",
    },
    {
        "phrase": "the archer seeks the cause in himself",
        "work": "Analects",
        "ref": "James Legge, Book III",
    },
    {
        "phrase": "to action alone hast thou a right",
        "work": "Bhagavad Gita",
        "ref": "public-domain English tradition",
    },
    {
        "phrase": "as a lamp in a windless place",
        "work": "Bhagavad Gita",
        "ref": "public-domain English tradition",
    },
    {
        "phrase": "evenness of mind is yoga",
        "work": "Bhagavad Gita",
        "ref": "public-domain English tradition",
    },
    {
        "phrase": "the self is friend and enemy",
        "work": "Bhagavad Gita",
        "ref": "public-domain English tradition",
    },
]


TAROT_CARDS = [
    ("jester", "The Jester", "Begin without over-explaining. Let curiosity and a little risk move before the stale answer arrives."),
    ("magician", "The Magician", "Use the tool already in your hand. Turn intention into a visible move."),
    ("high-priestess", "The High Priestess", "Let silence carry information. Notice what is withheld, reflected, or almost said."),
    ("empress", "The Empress", "Favor growth, appetite, comfort, and embodied detail. Make the scene feel lived in."),
    ("emperor", "The Emperor", "Look for structure, borders, rank, and responsibility. Act through order or test it."),
    ("hierophant", "The Hierophant", "Let custom, teaching, ritual, or office matter. Ask what the table believes is proper."),
    ("lovers", "The Lovers", "Make choice relational. Let attraction, loyalty, friction, or divided allegiance shape the move."),
    ("chariot", "The Chariot", "Pick a direction and commit. Tension can stay unresolved if momentum is clear."),
    ("strength", "Strength", "Use patience before force. Let restraint, courage, or gentleness become active."),
    ("hermit", "The Hermit", "Narrow the light. Seek one true detail instead of a broad explanation."),
    ("wheel", "The Wheel", "Let timing matter. Treat reversal, coincidence, or changing fortune as live texture."),
    ("justice", "Justice", "Balance cause and consequence. Make a clean distinction and let it cost something."),
    ("hanged-one", "The Hanged One", "Try the inverted angle. Delay, sacrifice, or surrender may reveal the next move."),
    ("death", "Death", "Let something end plainly. Make room by cutting the stale continuation."),
    ("temperance", "Temperance", "Blend unlike elements. Seek proportion, pacing, and a third way."),
    ("devil", "The Devil", "Notice appetite, bondage, leverage, or the bargain nobody wants to name."),
    ("tower", "The Tower", "Let false stability crack. Reveal pressure through a sudden visible consequence."),
    ("star", "The Star", "Leave a clean line of hope. Use distance, repair, or a small honest light."),
    ("moon", "The Moon", "Trust uncertainty without solving it. Let fear, dream logic, or mistaken shapes color perception."),
    ("sun", "The Sun", "Make something bright, direct, and hard to hide from. Clarity can be disruptive."),
    ("judgement", "Judgement", "Let a call be heard. Bring return, reckoning, or awakening into the choice."),
    ("world", "The World", "Close a circle. Let the move acknowledge the whole pattern, not just the next beat."),
]


TAROT_LENSES = [
    {
        "deck_id": "waite-key",
        "deck_name": "Waite Key",
        "lens": "Read the symbol as a quiet inner weather, not an order.",
        "source_note": "Public-domain Waite-inspired major-arcana lens.",
    },
    {
        "deck_id": "marseille-line",
        "deck_name": "Marseille Line",
        "lens": "Keep the image spare and concrete; let posture and rank do the work.",
        "source_note": "Project-authored Marseille-style line reading.",
    },
    {
        "deck_id": "etteilla-oracle",
        "deck_name": "Etteilla Oracle",
        "lens": "Treat the card like an omen in motion: practical, pointed, and a little strange.",
        "source_note": "Project-authored Etteilla-style oracle reading.",
    },
    {
        "deck_id": "golden-dawn-room",
        "deck_name": "Golden Dawn Room",
        "lens": "Look for hidden structure, element, threshold, and initiation.",
        "source_note": "Project-authored ceremonial-symbol reading.",
    },
    {
        "deck_id": "table-deck",
        "deck_name": "Table Deck",
        "lens": "Translate the card into table behavior: pacing, attention, risk, and voice.",
        "source_note": "Project-authored Agents of Glass table reading.",
    },
]


DEFAULT_TAROT_DURATION_TURNS = 25


def is_play_mode(mode: str | None) -> bool:
    normalized = (mode or "").strip().lower()
    return bool(normalized) and normalized not in NON_PLAY_MODES


def verse_for_turn(*, campaign_id: str, actor: str, turn_number: int) -> dict[str, str]:
    idx = _stable_index(
        ["verse", campaign_id, actor, str(turn_number)],
        len(VERSE_PHRASES),
    )
    return dict(VERSE_PHRASES[idx])


def tarot_for_seed(
    *,
    campaign_id: str,
    actor: str,
    turn_number: int,
) -> dict[str, str]:
    deck = TAROT_LENSES[
        _stable_index(["tarot-deck", campaign_id, actor, str(turn_number)], len(TAROT_LENSES))
    ]
    card_id, card_name, meaning = TAROT_CARDS[
        _stable_index(["tarot-card", campaign_id, actor, str(turn_number)], len(TAROT_CARDS))
    ]
    return {
        "deck_id": deck["deck_id"],
        "deck_name": deck["deck_name"],
        "card_id": card_id,
        "card_name": card_name,
        "influence": f"{meaning} {deck['lens']}",
        "source_note": deck["source_note"],
    }


def _stable_index(parts: list[str], modulo: int) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % modulo
