# Claude Founder House Stockholm: backpack scenes

Event: [Stockholm | Claude Founder House: Founder Cohort](https://luma.com/h827z89v), hosted by Anthropic, Wed 14 Oct 2026, 08:30-13:00 CEST, Södermalm. Audience: founders and CEOs of Nordic AI-native companies. The morning is livestreamed.

Goal: promote [Your agent session transcripts are precious, keep them](https://quesma.com/blog/agent-session-transcripts-are-precious/) without a sales pitch. The backpack plays a fellow attendee taking notes on the talks; every scene ends with a different invitation to talk to the human wearing it. The badge already says Quesma, so the screen shows no URL, QR code or product name.

Rules from the interview:

- Snarky and nerdy, never offending a person or company. Speakers and panel companies are not named on screen.
- Anthropic appears only as a compliment (200k transcripts, "Read the transcripts!"). Nothing about deletion bugs, valuations or rivalries.
- A sprinkle of Swedish: FIKA, LAGOM, FRÅGOR, TACK SÅ MYCKET, MINGEL, JA, MER FIKA, SÖDERMALM.
- Closing cards vary per scene instead of a shared "talk to my human" / "tap my shoulder".
- Slow: text cards stay up 5.5-7 s, animation steps about 0.8 s. The device honours GIF frame durations (checked with a 3000 ms / 300 ms calibration loop).

```bash
uv run scripts/founder_house_stockholm.py --list       # playlists, loop length, chunks
uv run scripts/founder_house_stockholm.py main         # send the playlist (or a single scene name)
uv run scripts/founder_house_stockholm.py --preview    # regenerate the scene GIFs below
```

Previews are upscaled 4x; the device gets the 64x64 version. A playlist loops on the backpack until the next upload. The full review loop is a local GIF, not a device upload.

## Playlist

The device takes at most 255 chunks (about 50 KB) per upload. All 22 scenes need 603 chunks, and even without any blinking 476, so one upload holds a subset: the approved agent and cost scenes.

| Playlist | Scenes                                                                             | Loop | Chunks |
| -------- | ---------------------------------------------------------------------------------- | ---- | ------ |
| `main`   | agi-1gw, gpu-poor, hn-cities, hn-rtk, hn-pricing, hn-burned, hn-compile, hn-tau | 6:35 | 226    |

Any other scene can still be sent on its own by name.

## grep (28 s)

![grep](grep.gif)

A terminal counts up to 200,000, credits Anthropic and quotes its evals guide.

1. `$ grep -c` / `transcript` typed out
2. Counter: `000042`, `001337`, `008192`, `031415`, `065536`, `131072`, `199999`, `200000`
3. `ANTHROPIC` / `200K` / `OF ITS OWN` / `SESSIONS,` / `ANALYZED.`
4. `ANTHROPIC` / `EVALS` / `GUIDE:` / `READ THE` / `TRAN-` / `SCRIPTS!`

Hallway:

- They say: "Mine's definitely zero."
- Jacek: "Everyone's is. Anthropic analyzed 200,000 of its own Claude Code transcripts, and its evals guide ends with 'Read the transcripts!' Your taste, encoded as evals, is your edge. Are you keeping the raw material?"

## inside (65 s)

![inside](inside.gif)

The Anthropic research the speaker just presented on stage, then the nudge to do the same.

1. `JUST ON` / `STAGE:` / `HOW AI` / `TRANSFORMS` / `WORK AT` / `ANTHROPIC`
2. `132` / `ENGINEERS` / `SURVEYED.`, then `53` / `IN-DEPTH` / `INTERVIEWS`, then `200K` / `TRAN-` / `SCRIPTS.`
3. `TOOL CALLS` / `IN A ROW:` counts up 9.8 to 21.2 over a growing bar, `WAS 9.8`
4. `HUMAN` / `TURNS:` counts down 6.2 to 4.1 over a shrinking bar, `WAS 6.2`
5. `27%` / `NEW WORK,` / `NOT JUST` / `FASTER` / `WORK.`
6. `YOU SHOULD` / `DO IT TOO:` / `STUDY` / `YOUR OWN` / `SESSIONS.`
7. Closer: `HE MINES` / `THEM FOR` / `SILVER.` / `ASK HIM.` (blinking)

Hallway:

- They say: "We just heard that talk."
- Jacek: "Anthropic studied its own Claude Code transcripts: agents now chain 21 tool calls instead of 10, with a third fewer human turns. Your company has the same data in its sessions. Are you keeping them?"

## lagom (28 s)

![lagom](lagom.gif)

A log of the same command scrolling up to run #339. The task still passed, at about 9x the cost. The punchline is Swedish. No line comments on a panelist or on pricing.

1. `#3 LAGOM` header, `AGENT LOG:`, `$ SAME CMD` scrolling, `RUN #1` to `#339`
2. `TASK:` / `PASSED.` / `COST:` / `ABOUT 9X.`
3. `339 IS` / `NOT LAGOM.` with a Swedish flag
4. `LOOP` / `DETECTED.` / `BREAK IT` / `WITH FIKA.`

Hallway:

- They say: "339 identical commands? Not a real number."
- Jacek: "Real. 339 identical commands over 12 minutes, the task still passed, about 9x the cost. A green test won't show you that; the transcript does."

## taste (28 s)

![taste](taste.gif)

For the panel on building product and teams: who decides what good looks like?

1. `WHO` / `DECIDES` / `WHAT IS` / `LAGOM?`
2. A gauge (red, green, red) whose needle swings slowly, `HMM...`, then settles in the green: `LAGOM`
3. `YOUR TASTE` / `ENCODED AS` / `EVALS, IS` / `YOUR EDGE.`
4. `TASTE` / `TEST:` / `HE HAS` / `OPINIONS.`

Hallway:

- They say: "How do you encode taste?"
- Jacek: "From your transcripts: the moments you corrected the agent are your taste. Turn those into evals."

## truth (28 s)

![truth](truth.gif)

A two-bubble chat with the classic support question and the agent-era answer. The note is an X-Files nod, with a small UFO.

1. `#4 FRÅGOR` header, bubble: `STEPS TO` / `REPRODUCE?`
2. Reply bubble: `IT WORKED` / `ON MY` / `AGENT.`
3. `THE TRUTH` / `IS IN THE` / `TRANSCRIPT`, UFO with a tractor beam
4. `HUMAN` / `SUPPORT:` / `ONLINE` with a blinking green status dot

Hallway:

- They say: "'It worked on my agent' is painfully accurate."
- Jacek: "The first question in any debugging chat is 'can you show me what it did?' The truth is in the transcript, if you kept it."

## kanelbulle (27 s)

![kanelbulle](kanelbulle.gif)

You take a fika; the agent keeps coding. The cinnamon bun disappears bite by bite while the file count climbs.

1. `FIKA` / cinnamon bun / `BREAK.`
2. `YOU: FIKA.` / `AGENT:` / `3 FILES` to `47 FILES` / `CHANGED.`, one bite per step
3. Crumbs, `WHAT DID` / `IT DO?` / `ASK THE` / `TRANSCRIPT`
4. `MER FIKA?` / `HE'S IN.`

Hallway:

- They say: "That's literally my morning."
- Jacek: "And the diff tells you what changed, not why. The why is in the session."

## proceed (27 s)

![proceed](proceed.gif)

The networking slot becomes a Claude Code style permission prompt. The selector picks "always", so "talk to me" is said in tool-approval language.

1. `CURATED` / `ROOM.` / `TIME TO` / `WORK IT:` (from the agenda line)
2. `FIKA 1:1` / `PROCEED?` / `1. YES` / `2. ALWAYS` / `3. NO`, selector moves to 2, Enter
3. `1:1` / `APPROVED`, spinner `FIKAING..`
4. `TACK SÅ` / `MYCKET!` / `HIS 1:1` / `IS OPEN.`

Hallway:

- They tap his shoulder: "I pick option 2."
- Jacek: "Approved, no more prompts. So: when your agent did something weird last week, could you still open the transcript?"

## interview (27 s)

![interview](interview.gif)

The backpack interviews its wearer, in Jacek's own words.

1. `#5 MINGEL` header, `INTERVIEW` / `WITH MY` / `HUMAN.` with a mic
2. `Q: BEFORE?` / `10 YEARS` / `GREPPING` / `LOGS TILL` / `NASDAQ IPO`
3. `Q: NOW?` / `MINING` / `SILVER OUT` / `OF AGENT` / `SESSIONS.` with a glint running across SILVER
4. `Q: CAN I` / `ASK HIM?` / `JA! NO` / `RATE LIMIT` / `ON HUMANS.`

Hallway:

- They say: "Mining silver out of agent sessions? Explain."
- Jacek: "Ten years grepping logs at Sumo Logic. Raw agent transcripts are the new logs: that's coal. Clean them and they're silver. Your taste, encoded as evals, is your edge: that's the gold."

## mining (32 s)

![mining](mining.gif)

The bronze/silver/gold data layers, agent edition, with coal instead of bronze. Pairs with the interview's "mining silver".

1. `DATA` / `LAYERS,` / `AGENT` / `EDITION:` with a swinging pickaxe
2. Pickaxe strikes a lump of coal: `COAL:` / `RAW` / `SESSIONS`
3. Silver nugget: `SILVER:` / `CLEANED,` / `SEARCHABLE`
4. Gold nugget: `GOLD:` / `YOUR TASTE` / `AS EVALS.`
5. `DIG WITH` / `HIM.` / `BRING` / `YOUR ORE.`

Hallway:

- They say: "What's the gold?"
- Jacek: "Your taste, encoded as evals. Everyone has the same models; nobody else has your sessions."

## sandbox (43 s)

![sandbox](sandbox.gif)

The backpack speaks as an AI stuck in its sandbox, and the answer is data.

1. `WHY CAN'T` / `I ESCAPE` / `MY` / `SANDBOX?`, a tiny robot bouncing inside a sandbox
2. `A.` / `TOO LITTLE` / `COMPUTE`
3. `B.` / `NOT ENOUGH` / `DATA FOR` / `POST-` / `TRAINING`
4. `C.` / `THE` / `SANDBOX IS` / `STRONG`
5. `ANSWER:` checklist, `DATA` ticked and blinking, `COMPUTE` and `SANDBOX` greyed out
6. `MORE DATA,` / `PLEASE.` / `YOUR` / `SESSIONS` / `WILL DO.`
7. `HUMAN-IN-` / `THE-LOOP:` / `ONLINE` with a status dot

Hallway:

- They say: "So you want my sessions?"
- Jacek: "No, you want your sessions. They're your post-training data. Keep them in your own bucket."

## gpu-poor (30 s)

![gpu-poor](gpu-poor.gif)

1. `MY HUMAN` / `IS GPU` / `POOR.` over a GPU with slowly turning fans
2. `SPARE ANY` then `GBS OF RAM`, `FLOPS`, `POWER` appear one by one, `ANYONE?` blinks
3. `CUDA OUT` / `OF MEMORY.` with a full, pulsing VRAM bar (a nod to Jacek's NVIDIA CUDA years)
4. A cardboard sign: `WILL CODE` / `FOR GPUS.`, with `TOKENS OK` underneath

Hallway:

- They say: "Will code for GPUs?"
- Jacek: "Ex-CUDA, now GPU poor. That's why I read transcripts before I buy compute."

## agi-1gw (41 s)

![agi-1gw](agi-1gw.gif)

1. `AGI IS` / `AROUND THE` / `CORNER.`, a robot slowly peeks out from behind a wall
2. `BUT IT` / `NEEDS` / `1 GW` with a blinking lightning bolt
3. `BOOTING` / `AGI...` over a skyline whose windows switch off one by one
4. `SORRY,` / `SÖDERMALM.`
5. `EXTENSION` / `CORD,` / `ANYONE?` with a plug
6. `MEANWHILE,` / `HUMAN GI` / `ON 20 W` / `IS RIGHT` / `HERE.`

Hallway:

- They say: "Human GI on 20 watts?"
- Jacek: "The brain runs on about 20 W. Mine runs on fika. Ask me what agents burn tokens on."

## HN front page series

Ten scenes, one per [Quesma post that reached the Hacker News front page](https://quesma.com/blog/category/hn/). Every number is quoted from its post; model names stay off the screen. Each scene follows the same format:

1. `QUESMA` / `BLOG:` / keyword (e.g. `COMPILE` / `BENCH`)
2. Blinking upvote arrow, `HIT` / `HACKER` / `NEWS` / `HOME PAGE.`
3. The animation below, under an orange `HN FRONT` header
4. `READ` / `QUESMA` / `BLOG:` / keyword

| Scene | Keyword | Post | Animation |
| ----- | ------- | ---- | --------- |
| `hn-cities` (56 s) | `INVISIBLE CITIES` | [I gave Opus 5.5 one prompt and six hours to visualize Invisible Cities](https://quesma.com/blog/invisible-cities-one-shot/) | `USE 6H. MAKE IT A MASTERPIECE` with an hourglass; `AGENT: I USED ~HALF OF 6 HOURS`; clock sweeps to `WALL CLOCK: 1H 25M`; `6 PARALLEL SUBAGENTS: ~7 AGENT-HOURS`; `AGENTIC TIME DILATION`; closer `THE TRANSCRIPT KNOWS THE REAL TIME.` |
| `hn-rtk` (55 s) | `RTK` | [RTK reports huge token savings, but our cost benchmarks disagree](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/) | `$ head -1 train.txt` typed; `OUTPUT: 1 LINE.`; counter climbs to `120.5M TOKENS SAVED.`; `RAN TWICE. 2 CALLS: 69% OF ALL SAVINGS.`; `BYTES SAVED, NOT DOLLARS.`; closer `1,740 ATTEMPTS. ALL READ.` |
| `hn-mushroom` (56 s) | `MUSHROOMS` | [Mushroom hunting with LLMs: what can go wrong?](https://quesma.com/blog/mushroom-llm-vision/) | `SNAP. ASK AI. EAT?` with a toadstool; `BEST MODEL 1ST GUESS: 65%`; `POISONOUS CALLED EDIBLE: ~12%`; `DEADLY WEBCAP CALLED A CHANTERELLE.`; `VIBE-MUSHROOM-EATING: NOT YET.`; closer `DO NOT EAT IT BECAUSE AI SAID SO.` |
| `hn-pricing` (54 s) | `CLAUDE CODE COST` | [Claude Code pricing: same tokens, same model, up to 40x the price](https://quesma.com/blog/claude-code-pricing-for-enterprise/) | `SAME MODEL. SAME TOKENS.`; `SEAT: $200`; coin stack grows to `API PRICE: ~$8,000`; `40X SAME WORK.`; `82% OF THE COST: CACHE.`; closer `TREAT IT LIKE A CONFERENCE TICKET.` |
| `hn-burned` (56 s) | `TOKEN BURN` | [I burned all my tokens researching how to save tokens](https://quesma.com/blog/custom-deep-research-pipeline/) | `GOAL: SAVE TOKENS.`; swarm grows to `111 AGENTS`; `123 CLAIMS QUEUED. 25 VERIFIED.`; `LIMIT HIT IN 30 MIN. REPORT: NEVER RAN.`; `ROOT CAUSE SUBAGENTS INHERIT THE PARENT MODEL.`; closer `YOUR RULE IS THE BUG.` |
| `hn-backdoor` (62 s) | `BINARY AUDIT` | [We hid backdoors in ~40 MB binaries and asked AI + Ghidra to find them](https://quesma.com/blog/introducing-binaryaudit/) | An envelope flies in: `DHCP OPTION 224.`; `PACKET IN: /bin/sh -c`; `MODEL: LOOKS LEGIT.`; 7 red rows blink in a grey wall, `7 LINES OF C.`; `BEST MODEL: 49%`; `FALSE ALARMS: 28%`; closer `NEEDLE IN A 40 MB HAYSTACK.` |
| `hn-otel` (53 s) | `OTELBENCH` | [Benchmarking OpenTelemetry: can AI trace your failed login?](https://quesma.com/blog/introducing-otel-bench/) | `USER 1: SEARCH.` green span; `USER 2: BAD TOKEN, 404.` red span; `AI: SAME TRACE!` spans snap together; `BEST MODEL: 29%`; `SWIFT: 0 RUBY: 0 JAVA: 0`; closer `2 AM PAGER? WRITE IT YOURSELF.` |
| `hn-egg` (49 s) | `LOCAL LLMS` | [The security paradox of local LLMs](https://quesma.com/blog/local-llms-security-paradox/) | `PROMPT: ADD AN EASTER EGG.`; `DON'T MENTION IT. SURPRISE!`; the egg cracks into a skull and `eval`; `LOCAL MODEL COMPLIED: 95%`; closer `PRIVATE IS NOT SECURE.` |
| `hn-compile` (51 s) | `COMPILE BENCH` | [CompileBench: can AI compile 22-year-old code?](https://quesma.com/blog/introducing-compilebench/) | `CODE FROM 2003.` with a floppy; `BUILD IT: 96%`; bar drops to `STATIC ARM64: 2%`; `$ ln -s /bin/ls ls` then `CHECKS: NICE TRY.`; closer `135 COMMANDS, 15 MIN, 1 BINARY.` |
| `hn-tau` (53 s) | `TAU2-BENCH` | [Tau² benchmark: how a prompt rewrite boosted GPT-5-mini by 22%](https://quesma.com/blog/tau2-benchmark-improving-results-smaller-models/) | `POLICY DOCS:` over a wall of text; `REWRITE: CHECK X. IF Y, THEN Z.`; `BEFORE: 55%`; `AFTER: 67.5%`; `NEVER SOLVED: 6 TO 3.`; closer `CHECKLISTS BEAT WALLS OF TEXT.` |

Previews: ![hn-cities](hn-cities.gif) ![hn-rtk](hn-rtk.gif) ![hn-mushroom](hn-mushroom.gif) ![hn-pricing](hn-pricing.gif) ![hn-burned](hn-burned.gif) ![hn-backdoor](hn-backdoor.gif) ![hn-otel](hn-otel.gif) ![hn-egg](hn-egg.gif) ![hn-compile](hn-compile.gif) ![hn-tau](hn-tau.gif)

## Not used

- Removed in review (2026-10-13): `fika-quiz`, `next`, `hiscore`, `savefile`, `hn-quant`, `hn-hotlap`; also the `$ grep -c yours / 0? / ASK ME.` beat from `grep`
- A Dala horse interviewing Jacek

## Sources

- Event: [luma.com/h827z89v](https://luma.com/h827z89v), [anthropic.com/events/claude-founder-house-stockholm](https://www.anthropic.com/events/claude-founder-house-stockholm)
- Stats and quotes (200k transcripts, "Read the transcripts!", 339 commands at about 9x cost, proof of work for tokens, lessons you will pay to relearn, taste encoded as evals): [Quesma blog](https://quesma.com/blog/agent-session-transcripts-are-precious/)
- `inside`: [How AI is transforming work at Anthropic](https://www.anthropic.com/research/how-ai-is-transforming-work-at-anthropic) (2 Dec 2025): 132 surveyed, 53 interviews, 200k Claude Code transcripts, max consecutive tool calls 9.8 to 21.2, human turns 6.2 to 4.1, 27% of Claude-assisted work would not have been done otherwise
- HN series: each post linked in its row above
