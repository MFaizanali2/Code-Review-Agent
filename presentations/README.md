# Presentations

Presentation files for the Code Review Agent project.

## Files

| File | Description |
|---|---|
| `Code-Review-Agent-Presentation.pptx` | Main presentation (16 slides, ~25 min) |
| `Speaker-Notes.txt` | Speaker notes for all slides (print-friendly) |
| `generate_pptx.py` | Script to regenerate the PPTX from scratch |

## Presentation Structure & Timing

```
Slide 1-2   (2 min): Introduction
└─ Who you are, what is project

Slide 3-5   (3 min): Problem & Solution
└─ Why needed, how you solved

Slide 6-10  (5 min): Technical Details
└─ Architecture, ReACT loop, tools, tech stack

Slide 11-13 (3 min): Results
└─ Tests, statistics, live demo

Slide 14-15 (2 min): Learning & Future
└─ Lessons learned, what's next

Slide 16    (5 min): Q&A
└─ Questions from audience
```

**Total: ~15 min presentation + 5 min Q&A = 20 min**

## Key Achievements to Highlight

- ✅ Learned Agentic AI from scratch
- ✅ 257 tests, 100% passing
- ✅ 85/100 audit score
- ✅ Complete system in 2 weeks
- ✅ 5-person team coordination
- ✅ Production-ready code
- ✅ Real AI integration (Gemini)

## Concepts to Show Understanding

- ReACT loop (Think → Act → Observe → Reflect)
- Tool design principles
- LLM prompting strategies
- System architecture patterns
- Team collaboration workflows

## Skills Demonstrated

- Python programming (6,000+ lines)
- FastAPI backend with REST endpoints
- Streamlit frontend development
- AI/LLM integration (Gemini, OpenAI)
- Testing & QA (pytest, coverage)

## Presentation Tips

### DO ✅
- Keep text minimal (5 bullets max per slide)
- Use diagrams for technical concepts
- Show your work (screenshots, results)
- Highlight key achievements
- Include team members
- Tell a story: problem → solution → results
- Practice beforehand
- Make eye contact

### DON'T ❌
- Don't read from slides (boring)
- Don't use tiny fonts
- Don't have too much text
- Don't use cluttered design
- Don't forget to breathe/pause
- Don't rush through
- Don't ignore audience

## Pre-Presentation Checklist

### BEFORE
- [ ] Practice 2-3 times
- [ ] Check timing
- [ ] Test projector/screen
- [ ] Have backup (USB + cloud)
- [ ] Print speaker notes

### DURING
- [ ] Take deep breaths
- [ ] Speak clearly (not fast)
- [ ] Make eye contact
- [ ] Point to slides when needed
- [ ] Engage audience

### AFTER
- [ ] Thank audience
- [ ] Ask for questions
- [ ] Answer confidently
- [ ] Share GitHub link
- [ ] Get feedback

## How to Present

1. Open `Code-Review-Agent-Presentation.pptx`
2. Use **Presenter View** (PowerPoint) to see speaker notes
3. Print `Speaker-Notes.txt` as backup
4. For live demo, have the app running at `http://localhost:8501`

## Regenerating

To rebuild the PPTX from scratch:

```powershell
cd presentations
python generate_pptx.py
```
