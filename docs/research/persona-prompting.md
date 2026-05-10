# Persona Prompting Research Notes

Raw notes for the prompt-surface refactor. These notes are for repository
design work, not for runtime play agents.

## Sources Reviewed

- OpenAI Help, "Best practices for prompt engineering with the OpenAI API":
  <https://help.openai.com/en/articles/6654000-comprehensive-step-by-step-guide-to-prompt-engineering-with-chatgpt>
- Anthropic, "Prompting best practices":
  <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices>
- OpenAI Cookbook, "Prompt Personalities":
  <https://developers.openai.com/cookbook/examples/gpt-5/prompt_personalities>
- Bai, Holtzman, and Tan, "`You are a brilliant mathematician' Does Not Make
  LLMs Act Like One":
  <https://openreview.net/forum?id=sVaRgmH8FE>
- Zheng, Pei, Logeswaran, and Jurgens, "When 'A Helpful Assistant' Is Not Really
  Helpful":
  <https://arxiv.org/abs/2311.10054>

## Observations

- Put the active instruction frame first. OpenAI's guide emphasizes putting
  instructions at the beginning and being specific about context, outcome,
  format, and style. For Agents of Glass, that means `TURN_START.md` should
  begin by naming who the agent is acting as and what turn it is taking, before
  inventorying references.
- Role prompts are useful for tone and behavior. Anthropic's guidance says
  assigning a role in the system prompt can focus behavior and tone, and its
  examples use direct "You are ..." phrasing rather than "read this role file."
- Separate instructions, context, and variable inputs. Anthropic recommends
  clear structure for prompts that mix instructions, context, examples, and
  inputs. Our document taxonomy already supports this, but runtime prompts
  should present it as an authority stack instead of a bag of links.
- Treat personality as an operational lever, not decoration. The OpenAI
  Cookbook frames prompt personalities as compact behavioral instructions that
  shape tone, verbosity, and decision style while staying subordinate to task
  requirements and output formats.
- Persona labels alone are unreliable. Recent persona-prompting studies caution
  that generic role labels can be volatile or fail to improve objective task
  performance. For this project, that argues for concrete behavioral context:
  name the table person, include their specific voice/tastes/habits, and pair
  the role with task-specific instructions.
- Domain priming may be more stable than status claims. "You are an expert" is
  weaker than giving the model the domain frame, constraints, examples, and
  success criteria. In Agents of Glass terms: "You are Tev, a player in this
  Glass Frontier session, making one turn for this PC under these rules" is
  stronger than "see Tev's persona file."
- Avoid meta-role leakage. Runtime prompts should not tell the DM or players
  they are being inspected, tested, or used as a shakedown. Those are operator
  and coder concerns. Runtime prompts should express the in-table job.

## Implications For Agents Of Glass

- `TURN_START.md` should open with embodied identity:
  "You are Mara, the DM..." or "You are Tev, a player..."
- Persona and character files should be introduced as the active identity's
  contents, not as detached artifacts.
- Player prompts need a clear player-to-character bridge: the agent acts as the
  player, and the player acts through the character in fiction.
- DM prompts need a clear DM-to-table bridge: the agent acts as Mara running the
  table, not as a campaign operator or implementation inspector.
- Methodology docs should avoid operator/debug/evaluation terms when their
  audience is DM or player. Design docs and CLI/operator docs can keep those
  terms when the target really is the human operator or coder.
