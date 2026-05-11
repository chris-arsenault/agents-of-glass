import { useMemo } from "react";

import { useSessionStore } from "../store/sessionStore";
import { PlayerColumn } from "./PlayerColumn";

export function PlayerRow() {
  const playerOrder = useSessionStore((state) => state.playerOrder);
  const characters = useSessionStore((state) => state.characters);
  const playerIds = useMemo(() => {
    const extras = characters
      .map((character) => character.player_id)
      .filter((id) => !playerOrder.includes(id));
    return [...playerOrder, ...extras].slice(0, 4);
  }, [characters, playerOrder]);
  return (
    <section className="player-row">
      {playerIds.map((playerId) => (
        <PlayerColumn key={playerId} playerId={playerId} />
      ))}
    </section>
  );
}
