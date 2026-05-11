export type AgentTone = "mara" | "tev" | "sumi" | "renno" | "kit" | "neutral";

const KNOWN_TONES: Record<string, AgentTone> = {
  mara: "mara",
  tev: "tev",
  sumi: "sumi",
  renno: "renno",
  kit: "kit",
  dm: "mara",
};

export function toneFor(identifier?: string | null): AgentTone {
  if (!identifier) {
    return "neutral";
  }
  const key = identifier.toLowerCase().trim();
  if (KNOWN_TONES[key]) {
    return KNOWN_TONES[key];
  }
  for (const [agent, tone] of Object.entries(KNOWN_TONES)) {
    if (key.includes(agent)) {
      return tone;
    }
  }
  return "neutral";
}

export function sigilFor(identifier?: string | null): string {
  if (!identifier) {
    return "··";
  }
  const cleaned = identifier.replace(/[^a-zA-Z]/g, "");
  if (cleaned.length === 0) {
    return "··";
  }
  return cleaned.slice(0, 2).toUpperCase();
}

export const AGENT_DISPLAY: Record<AgentTone, string> = {
  mara: "Mara",
  tev: "Tev",
  sumi: "Sumi",
  renno: "Renno",
  kit: "Kit",
  neutral: "—",
};
