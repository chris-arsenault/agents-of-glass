---
title: Naming Conventions
type: culture
tags: [social-structure]
prominence: mythic
registry: true
---

# Naming Conventions

Names in the Kaleidos system are primarily cultural, not species-based. Culture determines naming pattern. Species occasionally influences names as a secondary layer — traditional species-rooted names used as throwbacks, ceremonial names, or by people making a deliberate statement.

Each domain below follows the `name-forge` schema: **phonology** (sound inventory), **morphology** (word construction), **style** (presentation rules).
**Structural variety across traditions:**

| Tradition | Structure | Example |
|-----------|-----------|---------|
| Sithari | Personal + Family (formal two-part) | *Senna Korvanis* |
| Hab-Worlder | Given + Hab-marker (clipped two-part) | *Dern Talish* |
| Orcish | Mononym (one earned name) | *Goruth* |
| Gnomish | Apostrophe compound (resonance breaks) | *T'vekis* |
| Fae | Epithet-primary + breathy true name | *The Held Stillness* / *Eshaia* |
| Elven | Chain patronymic (name-of-name-of-name) | *Thaliraea ve Samaethis ve Loriendi* |

---

## Cultural Domains <!-- Naming -->

### Sithari

The system's formal register. Old-world gravitas.

```json
{
  "id": "sithari_npc",
  "cultureId": "sithari",
  "appliesTo": { "kind": ["npc"], "subKind": [], "tags": [] },
  "phonology": {
    "consonants": ["s", "t", "r", "l", "n", "m", "v", "k", "d", "th"],
    "vowels": ["a", "e", "i", "o", "ah", "eh"],
    "syllableTemplates": ["CV", "CVC", "CVV"],
    "lengthRange": [2, 3],
    "favoredClusters": ["th", "nd", "rv", "lm", "st"],
    "forbiddenClusters": ["gh", "kh", "aa", "ee"],
    "favoredClusterBoost": 1.3
  },
  "morphology": {
    "prefixes": ["Tal", "Kor", "Mer", "Val", "Sel", "Dor", "Ven"],
    "suffixes": ["indra", "aleth", "anis", "ova", "enis", "ira"],
    "structure": ["root", "root-suffix", "prefix-root-suffix"],
    "structureWeights": [0.3, 0.35, 0.35]
  },
  "style": {
    "capitalization": "title",
    "apostropheRate": 0,
    "hyphenRate": 0,
    "preferredEndings": ["a", "eth", "is", "en", "ith"],
    "preferredEndingBoost": 1.3,
    "rhythmBias": "flowing"
  }
}
```

**Name structure:** Personal name (2 syllables, generated from root) + Family name (3 syllables, generated from prefix-root-suffix). In formal contexts, family name comes first: *Korvanis Senna*. Personal name is intimate.

**Examples:** *Aven Talindra*, *Jorin Meraleth*, *Senna Korvanis*

**Shortened forms:** Sithari who leave the capital often clip their family name: *Lira Vashtenri* → *Lira Vasht*. This signals cosmopolitan rather than provincial.

---

### Hab-Worlder

Functional, compact. Names are tools, not statements.

```json
{
  "id": "habworlder_npc",
  "cultureId": "hab-worlder",
  "appliesTo": { "kind": ["npc"], "subKind": [], "tags": [] },
  "phonology": {
    "consonants": ["d", "t", "k", "r", "n", "m", "l", "s", "b", "sh"],
    "vowels": ["e", "a", "o", "u", "i"],
    "syllableTemplates": ["CVC", "CV", "VC"],
    "lengthRange": [1, 2],
    "favoredClusters": ["rn", "sh", "lk", "nt", "sk"],
    "forbiddenClusters": ["str", "spl", "thr"],
    "favoredClusterBoost": 1.2
  },
  "morphology": {
    "prefixes": [],
    "suffixes": [],
    "structure": ["root"],
    "structureWeights": [1.0]
  },
  "style": {
    "capitalization": "title",
    "apostropheRate": 0,
    "hyphenRate": 0,
    "preferredEndings": ["rn", "nt", "sk", "sh", "lt", "rk"],
    "preferredEndingBoost": 1.4,
    "rhythmBias": "staccato"
  }
}
```

**Name structure:** Given name (1-2 syllables) + Hab-name (1-2 syllables, often a short derivative of their hab or a functional marker). Hab-name is optional in local context — everyone on a hab knows where they are. No ornamentation.

**Examples:** *Dern Talish*, *Sable Korr*, *Dez Morrn*, *Shei Lush* (fae true name clipped for hab use)

---

## Species Domains <!-- Naming -->

Species naming traditions exist as a secondary layer. Most people use their culture's conventions. Species-traditional names appear as: ceremonial names, deliberate throwbacks, in species-majority communities, or as intimate names within species-specific social contexts.

### Orcish — Mononyms

One name. Earned, not given. Orcs receive a birth-sound from their parents — a placeholder, often just a syllable or two — and choose their true name when they're ready. The true name is the only name. Introducing yourself with one word and considering the matter settled is peak orc communication.

An orc using a two-part cultural name (e.g., a Sithari orc with a family name) is code-switching. Their mononym still exists underneath and is used in orc-to-orc contexts.

```json
{
  "id": "orc_species",
  "cultureId": "orc",
  "appliesTo": { "kind": ["npc"], "subKind": [], "tags": ["species-name"] },
  "phonology": {
    "consonants": ["k", "g", "r", "d", "b", "th", "n", "m", "v"],
    "vowels": ["a", "o", "u", "ah", "oh"],
    "syllableTemplates": ["CVC", "CVCC", "CV"],
    "lengthRange": [1, 3],
    "favoredClusters": ["rg", "th", "kr", "gv", "dk"],
    "forbiddenClusters": ["ss", "ff", "ll"],
    "favoredClusterBoost": 1.4
  },
  "morphology": {
    "prefixes": [],
    "suffixes": [],
    "structure": ["root"],
    "structureWeights": [1.0]
  },
  "style": {
    "capitalization": "title",
    "apostropheRate": 0,
    "hyphenRate": 0,
    "preferredEndings": ["ak", "orn", "uth", "a", "o", "urg"],
    "preferredEndingBoost": 1.5,
    "rhythmBias": "harsh"
  }
}
```

**Examples:** *Goruth*, *Thukra*, *Barok*, *Duva*, *Krenno*

**In cultural context:** An orc named *Goruth* raised Sithari might go by *Goruth Doraleth* professionally and *Goruth* among friends and family. An orc raised Hab-Worlder might just be *Goruth* everywhere, which suits both traditions fine.

---

### Gnomish — Apostrophe Compounds

Gnomish names contain harmonic breaks — points where the resonance of the name shifts, marked by an apostrophe in written form. This is not decoration. Gnomes hear these breaks as actual tonal shifts, the way a tuning fork changes pitch when you touch it to different surfaces. Non-gnomes usually pronounce the apostrophe as a brief glottal stop, which gnomes consider acceptable if inelegant.

```json
{
  "id": "gnome_species",
  "cultureId": "gnome",
  "appliesTo": { "kind": ["npc"], "subKind": [], "tags": ["species-name"] },
  "phonology": {
    "consonants": ["t", "k", "n", "l", "s", "r", "z", "v", "ch"],
    "vowels": ["i", "e", "a", "ih", "eh"],
    "syllableTemplates": ["CV", "CVC", "CVV"],
    "lengthRange": [2, 3],
    "favoredClusters": ["nk", "st", "lv", "rk", "ch", "zv"],
    "forbiddenClusters": ["gg", "kk", "tt"],
    "favoredClusterBoost": 1.3
  },
  "morphology": {
    "prefixes": [],
    "suffixes": ["ik", "en", "ist", "el", "is"],
    "structure": ["root", "root-suffix"],
    "structureWeights": [0.4, 0.6]
  },
  "style": {
    "capitalization": "title",
    "apostropheRate": 0.7,
    "hyphenRate": 0,
    "preferredEndings": ["ik", "en", "ist", "el", "is", "ek"],
    "preferredEndingBoost": 1.4,
    "rhythmBias": "staccato"
  }
}
```

**Name structure:** A single compound name with one or two apostrophe breaks. The segments before and after each break are generated independently and joined. Two-segment names are common; three-segment names indicate formality or old lineage.

**Examples:** *T'vekis*, *Chel'sten*, *Ri'navik*, *Zar'vel'eki*

**In cultural context:** A gnome raised Sithari might go by *Tivekis Meraleth* — the apostrophe smoothed out for non-gnome mouths, a Sithari family name appended. Among other gnomes, they're *T'vekis* and nobody needs more.

---

### Fae — Epithets

Fae are intermittently present. A fixed personal name feels wrong for a being that is sometimes a person and sometimes a room. The fae naming tradition reflects this: you are known by what you are *like*, not what you are *called*.

**Epithets** are the public name. Descriptive, poetic, referencing the fae's quality of presence — how they feel when they're diffuse, how they arrive when they cohere, what it's like to be near them. Epithets are given by others and can change over a lifetime.

**True names** exist but are intimate — shared with close bonds only. These follow the breathy phonology below and are used in fae-to-fae contexts and private moments.

```json
{
  "id": "fae_species",
  "cultureId": "fae",
  "appliesTo": { "kind": ["npc"], "subKind": [], "tags": ["species-name"] },
  "phonology": {
    "consonants": ["f", "s", "sh", "h", "l", "r", "w", "n", "th"],
    "vowels": ["a", "e", "i", "ai", "ei", "ou"],
    "syllableTemplates": ["V", "CV", "VCV", "CVV"],
    "lengthRange": [2, 3],
    "favoredClusters": ["sh", "th", "wh", "eil", "rai"],
    "forbiddenClusters": ["k", "t", "d", "b", "g", "ck", "kt", "gd"],
    "favoredClusterBoost": 1.3
  },
  "morphology": {
    "prefixes": [],
    "suffixes": ["ai", "esh", "ou", "ira", "en", "aia"],
    "structure": ["root-suffix"],
    "structureWeights": [1.0]
  },
  "style": {
    "capitalization": "title",
    "apostropheRate": 0,
    "hyphenRate": 0.3,
    "preferredEndings": ["ai", "esh", "ou", "ira", "en", "aia"],
    "preferredEndingBoost": 1.6,
    "rhythmBias": "soft"
  }
}
```

**Epithet examples:** *The Held Stillness*, *Warmth-at-Nine*, *Soft Landing*, *The One Who Arrives Slowly*

**True name examples:** *Eshaia*, *Louwen*, *Fei'shara*, *Shenai*, *Whoulen*

**In cultural context:** A fae raised Hab-Worlder might be called *Shei* by crewmates (a clipped version of their true name that fits hab naming) and *The Stillness* in formal contexts. The true name *Sheiren* is for intimates.

---

### Elven — Chain Patronymics (Historical)

Elven names are chains — your name, then your parent's name, then theirs, linked by *ve* ("of/from"). A full elven name could run ten generations deep. In practice, three links was common for everyday use, and the full chain was reserved for ceremony.

This tradition is extinct in public use — the elves are gone. Fragments surface in Echo River recordings. Scholars reconstruct partial chains from the surviving references.

```json
{
  "id": "elf_species",
  "cultureId": "elf",
  "appliesTo": { "kind": ["npc"], "subKind": [], "tags": ["species-name"] },
  "phonology": {
    "consonants": ["l", "r", "n", "th", "v", "s", "m", "d"],
    "vowels": ["a", "e", "i", "ae", "ai", "ea", "ia"],
    "syllableTemplates": ["CVV", "CVCV", "VCV", "CV"],
    "lengthRange": [3, 5],
    "favoredClusters": ["th", "ae", "ia", "nd", "lr"],
    "forbiddenClusters": ["gg", "kk", "ck", "bb"],
    "favoredClusterBoost": 1.4
  },
  "morphology": {
    "prefixes": ["Thal", "Ven", "Sam", "Lor", "Ael", "Mir"],
    "suffixes": ["aea", "ion", "ethis", "endi", "iel", "aith"],
    "structure": ["prefix-root-suffix", "root-suffix"],
    "structureWeights": [0.6, 0.4]
  },
  "style": {
    "capitalization": "title",
    "apostropheRate": 0,
    "hyphenRate": 0,
    "preferredEndings": ["ia", "ae", "ean", "ael", "ion", "aith"],
    "preferredEndingBoost": 1.5,
    "rhythmBias": "flowing"
  }
}
```

**Chain structure:** *Name ve Name ve Name*. Each link is independently generated. The chain reads youngest to oldest. *Thaliraea ve Samaethis ve Loriendi* = Thaliraea, child of Samaethis, child of Loriendi.

**In present-day usage:** Nobody uses elven chain names — but Echo River archivists have catalogued fragments. A scholar who recognizes the *ve*-linked pattern in a river recording knows they're hearing an elf.

---

## Slot Cultures (naming TBD) <!-- Applications -->

These cultures are defined but their naming conventions haven't been established yet.
| Culture | Structural instinct | Notes |
|---------|-------------------|-------|
| *7th-planet moon* | TBD | Water giant context likely shapes phonology — aquatic influence? |
| *Spiritual/druid* | TBD | Possibly nature-epithet influenced, but distinct from fae epithets |
| *Hyper-religious* | TBD | Liturgical naming? Theophoric elements? |
| *Syndicate* | TBD | Code names? Earned names like orc mononyms but darker? |
