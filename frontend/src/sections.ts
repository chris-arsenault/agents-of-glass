export const sectionTerms: Record<string, string[]> = {
  journal: ["journal", "players/"],
  lore: ["lore", "context", "summary"],
  arcs: ["arc", "previous"],
  scenes: ["scene", "table/scene", "transcript"],
  dm: ["dm/", "scratchpad", "prep"],
  audit: ["audit", ".jsonl"],
};

export function sectionLabel(section: string): string {
  const labels: Record<string, string> = {
    journal: "Journal",
    lore: "Lore",
    arcs: "Previous Arcs",
    scenes: "Scenes",
    dm: "DM Notes",
    audit: "Audit",
  };
  return labels[section] ?? "Files";
}
