import { selectPlayerIds, useSessionStore } from "../store/sessionStore";
import { PlayerColumn } from "./PlayerColumn";

export function PlayerRow() {
  const playerIds = useSessionStore(selectPlayerIds);
  return (
    <section className="player-row">
      {playerIds.map((playerId) => (
        <PlayerColumn key={playerId} playerId={playerId} />
      ))}
    </section>
  );
}
