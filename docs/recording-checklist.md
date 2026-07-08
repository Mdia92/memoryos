# Recording checklist — demo + deployment-proof videos

Two videos to record. This doc walks through the setup, the shot list,
and the post-recording steps. Read it once end-to-end before you sit down
to record.

---

## 30 minutes before recording

- [ ] Close every app that pops notifications (Slack, Discord, email, calendar reminders, iMessage, Steam).
- [ ] Turn on Do Not Disturb / Focus mode.
- [ ] Restart your browser to clear old tabs, extensions, and console noise.
- [ ] Full-screen the browser window; the sidebar chrome should not be visible.
- [ ] Set screen resolution to 1920×1080 (or 2560×1440 max). Anything larger scales badly.
- [ ] Use a clean profile (Chrome/Arc: create a new profile named "Demo"). Ad-blockers and cookie banners are fine to leave on.
- [ ] Test your mic — record 10 seconds, play it back. Ambient hiss and mouth sounds are more noticeable in the final video than you think.
- [ ] Set OBS / QuickTime / Loom to 60 fps if possible. Charts animate smoothly at 60.
- [ ] Have `docs/demo-script.md` open on your phone or a second monitor.

## Reset the live instance

Run these commands right before you hit record. They put the ECS
deployment in the exact state the script assumes:

```bash
export API=http://8.219.249.248
curl -X POST $API/api/demo/reset
curl -X POST $API/api/demo/seed -H "Content-Type: application/json" \
     -d '{"sessions":20}'
curl -X POST $API/api/eval/run -H "Content-Type: application/json" \
     -d '{"label":"demo","sessions":20,"seed":42}'
```

Then open three browser tabs at `http://8.219.249.248/`:

1. **Tab 1**: Ask page — pre-type the first question in the input but don't submit.
2. **Tab 2**: Auditor page — should show 1 open contradiction (remote vs office).
3. **Tab 3**: Dashboard — accuracy chart, LongMemEval chart, patterns all visible.

Do a dry-run walk-through end to end before hitting record. Every time.

---

## The main demo — beat-by-beat shot list (~3 min)

The `docs/demo-script.md` file has the narration verbatim. Below is the
*visual* choreography — what the camera should be doing.

**0:00–0:15 · Hook (Ask page)**
- Fade in on the Ask page, question already typed.
- Hit Enter. Both panels populate simultaneously.
- Mouse cursor sweeps left card first (traditional memory), then right card.
- Freeze on "One of these answers is a guess." for half a beat.

**0:15–0:45 · Evidence chain (Memory page)**
- Click Memory tab.
- Type "morning" in the filter (which we added on Day 2).
- One matching fact remains; click to expand.
- Zoom cursor to the confidence breakdown table.
- Ideally: use a screen zoom (macOS: Cmd+scroll) to briefly enlarge the breakdown numbers.

**0:45–1:15 · Evidence Auditor**
- Click Auditor tab.
- Show the open contradiction with both evidence sides.
- Hover over "This is correct" on the "office" side for a beat before clicking.
- Click. Toast appears in the top-right corner (SSE stream).
- Contradiction card slides into the "Resolved by user" section.
- Cut back to Ask, re-ask the same question. Confident answer this time.

**1:15–1:35 · Hybrid retrieval (Ask page)**
- Ask: *"Are there any calendar reschedule events in memory?"*
- Point at the `hybrid-retrieval` path badge next to the gate.
- Highlight one of the four cited event ids with similarity scores.
- The line "No hallucination surface" lands here.

**1:35–2:00 · Structural proof (Dashboard, accuracy chart)**
- Scroll to the accuracy chart.
- Trace the MemoryOS line from 42% up to 100% with your cursor.
- Trace the baseline line — point at the dip to 75%.
- Point at "Precision when acting: 100%" in the KPI row.

**2:00–2:20 · Public benchmark (Dashboard, LongMemEval chart)**
- Scroll further to the LongMemEval bar chart.
- Point at knowledge-update: MemoryOS 100% vs RAG 80%.
- Point at multi-session: 60% vs 50%.
- The line "This isn't our synthetic data — this is 500 public questions" lands here.

**2:20–2:35 · Cost tile (Dashboard, KPI row)**
- Point at the second KPI row: "Fast-path share 99.6%".
- Read the numbers: Qwen calls 2, deterministic ops 725.

**2:35–2:50 · Unprogrammed discovery (Dashboard, patterns)**
- Scroll to the discovered patterns panel.
- Four patterns are visible: reschedule + late-night + weekend + peak-hour.
- Read one aloud.

**2:50–3:10 · Close (Ask page split-view)**
- Cut back to the Ask page split-view answer.
- Read the closing line while looking at both cards.
- Fade to architecture.svg for the last 2 seconds.

## Common recording pitfalls

- **Bright red modals from browser extensions.** Even one "Update your password manager" popup ruins the take. Use a fresh profile.
- **The console log floods with warnings.** Close DevTools before recording.
- **Cursor jitter.** Move the mouse in short, deliberate arcs. Slow is better than fast.
- **Zoom-in without warning.** If you're using screen-zoom, give the viewer half a second to see the zoom start.
- **Reading the script.** Rehearse enough that you sound conversational. Reading from notes is instantly obvious.

---

## The deployment proof clip (~60 seconds, no narration required)

This one's simpler. Show, don't tell.

- **0:00–0:10** — Alibaba Cloud console → ECS Instances page. Highlight the running `memoryos` instance's status (Running, green dot), region (ap-southeast-1), public IP (8.219.249.248).
- **0:10–0:25** — SSH into the instance. Run:
  ```bash
  docker compose -f /root/memoryos/deploy/docker-compose.prod.yml ps
  ```
  Show four containers, three of them "(healthy)". Highlight the backend line specifically.
- **0:25–0:35** — From a local terminal (not the ECS SSH session):
  ```bash
  curl -sI http://8.219.249.248/
  curl -s http://8.219.249.248/health | jq
  ```
  Show the response with `Server: nginx`, security headers, `qwen_available: true`.
- **0:35–0:50** — Open a browser to `http://8.219.249.248/`. Dashboard loads.
- **0:50–0:60** — Open the Ask page. Ask any question. Point at the `qwen-plus` provider chip in the response — this proves Model Studio is being called live from the ECS deployment.

Code proof file (for the submission form's "code file demonstrating
Alibaba Cloud APIs" field): `backend/app/qwen_client.py` — every LLM and
embedding call targets DashScope on Alibaba Cloud.

---

## Post-recording

- [ ] Watch the whole video once at 1× speed. Any pause > 2 seconds is a cut.
- [ ] Trim dead air at the start and end.
- [ ] Add captions. YouTube's auto-caption is decent but review it — technical terms ("MemoryOS", "Qwen", "pgvector", "DashScope") often get mangled.
- [ ] Thumbnail: use the LongMemEval-vs-RAG bar chart or the 42%→100% accuracy chart as the base. Add the tagline "AI shouldn't remember more. It should remember correctly."
- [ ] Description: paste the "Text description" section from `SUBMISSION.md`, add the repo URL and live-instance URL, list the timestamps as chapter markers.
- [ ] Publish as public (unlisted won't satisfy the hackathon rules).
- [ ] Verify the link works in a private/incognito window before submitting.

## What to submit

- [ ] Devpost project page: title, tagline, "AI shouldn't remember more. It should remember correctly."
- [ ] Track: **1 — MemoryAgent**.
- [ ] Repo URL: https://github.com/Mdia92/memoryos.
- [ ] Live instance URL: http://8.219.249.248.
- [ ] Demo video link (the ~3 min one).
- [ ] Deployment proof link (the ~60 sec one).
- [ ] Code proof file link: `backend/app/qwen_client.py`.
- [ ] Text description: paste from `SUBMISSION.md`.
- [ ] MIT LICENSE detectable (badge should show automatically since it's at the repo root).
- [ ] Optional: submit the blog post URL for the Blog Prize.
