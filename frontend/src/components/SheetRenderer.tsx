import type { FileContent } from "../types";
import type { ReactNode } from "react";
import { classNames } from "../utils";
import { MarkdownBlock } from "./MarkdownBlock";

interface SheetRendererProps {
  file: FileContent | null;
  isLoading?: boolean;
}

interface MarkdownSection {
  heading: string;
  body: string;
}

interface ParsedMarkdown {
  body: string;
  frontmatter: Record<string, string>;
  sections: MarkdownSection[];
  title: string;
}

export function SheetRenderer({ file, isLoading }: SheetRendererProps) {
  if (!file?.content) {
    return (
      <div className="empty-state">
        {isLoading ? "Loading file" : "No file content"}
      </div>
    );
  }
  const parsed = parseMarkdown(file.content);
  if (isCharacterSheet(file, parsed)) {
    return <CharacterSheet parsed={parsed} />;
  }
  if (isPersonaSheet(file, parsed)) {
    return <PersonaSheet parsed={parsed} />;
  }
  return <MarkdownBlock content={file.content} />;
}

function CharacterSheet({ parsed }: { parsed: ParsedMarkdown }) {
  const overview = parseKeyValueList(preamble(parsed.body));
  const attributes = parseKeyValueList(sectionBody(parsed, "Attributes"));
  const skills = parseKeyValueList(sectionBody(parsed, "Skills"));
  const inventory = parseInventory(sectionBody(parsed, "Inventory"));
  const goals = parsePlainList(sectionBody(parsed, "Goals"));
  const tags = sectionBody(parsed, "Tags")
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

  return (
    <article className="sheet-view character-sheet">
      <SheetHeader
        kicker="Character"
        subtitle={overview["Archetype"] ?? overview["Organization role"]}
        title={parsed.title}
      />
      <dl className="sheet-stat-grid">
        {[
          "Player",
          "Species",
          "Culture",
          "Pronouns",
          "Level",
          "HP",
          "Momentum",
          "Organization role",
        ].map((key) => (
          <SheetStat key={key} label={key} value={overview[key]} />
        ))}
      </dl>
      <SheetSection title="Bio">
        <p>{sectionBody(parsed, "Bio")}</p>
      </SheetSection>
      <SheetSection title="Goals">
        <div className="sheet-card-list">
          {goals.map((goal) => (
            <p className="sheet-card" key={goal}>
              {goal}
            </p>
          ))}
        </div>
      </SheetSection>
      <div className="sheet-columns">
        <RankSection items={attributes} title="Attributes" />
        <RankSection items={skills} title="Skills" />
      </div>
      <SheetSection title="Inventory">
        <div className="inventory-grid">
          {inventory.map((item) => (
            <article className="inventory-card" key={item.name}>
              <header>
                <strong>{item.name}</strong>
                {item.qty && <span>{item.qty}</span>}
              </header>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </SheetSection>
      {tags.length > 0 && (
        <div className="sheet-tags">
          {tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      )}
    </article>
  );
}

function PersonaSheet({ parsed }: { parsed: ParsedMarkdown }) {
  const playStyle = parseBoldLeadList(sectionBody(parsed, "Play style"));
  const tics = parsePlainList(sectionBody(parsed, "Tics"));
  return (
    <article className="sheet-view persona-sheet">
      <SheetHeader
        kicker={`${parsed.frontmatter.role ?? "player"} overview`}
        subtitle={sectionBody(parsed, "Voice")}
        title={parsed.title}
      />
      <SheetSection title="Who">
        <p>{sectionBody(parsed, "Who he is") || sectionBody(parsed, "Who she is")}</p>
      </SheetSection>
      <SheetSection title="Play Style">
        <div className="persona-grid">
          {playStyle.map((item) => (
            <article className="persona-card" key={item.label}>
              <strong>{item.label}</strong>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </SheetSection>
      <SheetSection title="Tics">
        <ul className="sheet-list">
          {tics.map((tic) => (
            <li key={tic}>{tic}</li>
          ))}
        </ul>
      </SheetSection>
      <SheetSection title="What Gets Under Their Skin">
        <p>{sectionBody(parsed, "What gets under his skin") || sectionBody(parsed, "What gets under her skin")}</p>
      </SheetSection>
    </article>
  );
}

function SheetHeader({
  kicker,
  subtitle,
  title,
}: {
  kicker: string;
  subtitle?: string;
  title: string;
}) {
  return (
    <header className="sheet-header">
      <p className="eyebrow">{kicker}</p>
      <h3>{title}</h3>
      {subtitle && <p>{subtitle}</p>}
    </header>
  );
}

function SheetSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="sheet-section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}

function SheetStat({ label, value }: { label: string; value?: string }) {
  if (!value) {
    return null;
  }
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function RankSection({
  items,
  title,
}: {
  items: Record<string, string>;
  title: string;
}) {
  return (
    <SheetSection title={title}>
      <div className="rank-grid">
        {Object.entries(items).map(([label, value]) => (
          <div className={classNames("rank-chip", `rank-${slug(value)}`)} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </SheetSection>
  );
}

function parseMarkdown(content: string): ParsedMarkdown {
  const { body, frontmatter } = splitFrontmatter(content);
  const title = frontmatter.title ?? frontmatter.name ?? firstHeading(body) ?? "Sheet";
  return { body, frontmatter, sections: parseSections(body), title };
}

function splitFrontmatter(content: string) {
  const match = content.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!match) {
    return { body: content.trim(), frontmatter: {} };
  }
  const frontmatter = Object.fromEntries(
    match[1].split("\n").map((line) => {
      const [key, ...rest] = line.split(":");
      return [key.trim(), rest.join(":").trim()];
    }),
  );
  return { body: content.slice(match[0].length).trim(), frontmatter };
}

function parseSections(body: string): MarkdownSection[] {
  const sections: MarkdownSection[] = [];
  let current: MarkdownSection | null = null;
  for (const line of body.split("\n")) {
    if (line.startsWith("## ")) {
      current = { heading: line.replace(/^##\s+/, "").trim(), body: "" };
      sections.push(current);
    } else if (current) {
      current.body += `${line}\n`;
    }
  }
  return sections.map((section) => ({
    ...section,
    body: section.body.trim(),
  }));
}

function firstHeading(body: string): string | null {
  return body
    .split("\n")
    .find((line) => line.startsWith("# "))
    ?.replace(/^#\s+/, "")
    .trim() ?? null;
}

function preamble(body: string): string {
  return body.split("\n## ")[0].replace(/^# .+\n?/, "").trim();
}

function sectionBody(parsed: ParsedMarkdown, heading: string): string {
  return parsed.sections.find((section) => section.heading === heading)?.body ?? "";
}

function parseKeyValueList(body: string): Record<string, string> {
  return Object.fromEntries(
    body
      .split("\n")
      .map(parseBoldKeyValue)
      .filter((item): item is [string, string] => Boolean(item)),
  );
}

function parsePlainList(body: string): string[] {
  return body
    .split("\n")
    .filter((line) => line.startsWith("- "))
    .map((line) => line.replace(/^- /, "").trim());
}

function parseBoldLeadList(body: string): Array<{ label: string; text: string }> {
  return parsePlainList(body).map((line) => {
    const lead = parseBoldLead(line);
    return lead ? { label: lead[0], text: lead[1] } : { label: "Note", text: line };
  });
}

function parseInventory(body: string) {
  return parsePlainList(body).map((line) => {
    const item = parseBoldLead(line);
    const detailParts = item?.[1].split("—") ?? [];
    return {
      description: detailParts.slice(1).join("—").trim() || line,
      name: item?.[0] ?? line,
      qty: detailParts[0]?.trim(),
    };
  });
}

function parseBoldKeyValue(line: string): [string, string] | null {
  if (!line.startsWith("- **")) {
    return null;
  }
  const marker = ":**";
  const markerIndex = line.indexOf(marker);
  if (markerIndex < 0) {
    return null;
  }
  return [
    line.slice(4, markerIndex).trim(),
    line.slice(markerIndex + marker.length).trim(),
  ];
}

function parseBoldLead(line: string): [string, string] | null {
  if (!line.startsWith("**")) {
    return null;
  }
  const markerIndex = line.indexOf("**", 2);
  if (markerIndex < 0) {
    return null;
  }
  const rawLabel = line.slice(2, markerIndex).trim();
  const label = rawLabel.endsWith(":") ? rawLabel.slice(0, -1) : rawLabel;
  return [label, line.slice(markerIndex + 2).trim()];
}

function isCharacterSheet(file: FileContent, parsed: ParsedMarkdown): boolean {
  return (
    parsed.frontmatter.type === "character-display" ||
    file.path.endsWith("/public/character.md")
  );
}

function isPersonaSheet(file: FileContent, parsed: ParsedMarkdown): boolean {
  return parsed.frontmatter.role === "player" || parsed.frontmatter.role === "dm";
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
