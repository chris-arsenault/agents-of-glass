-- XP and level on characters.
--
-- xp:    cumulative awarded XP. Bumped via `glass character award-xp`.
-- level: the level the character has actually leveled up to. Lags xp until
--        the player runs `glass character level-up` to resolve choices
--        (which attribute to bump every 4 levels, d6 hp roll every level,
--        +1 momentum_ceiling every 5 levels). Threshold is 10 xp/level,
--        no max level.

ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS xp    int NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS level int NOT NULL DEFAULT 1;
