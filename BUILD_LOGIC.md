# BUILD_LOGIC.md - Agent Workthrough Protocol

## Build Criteria for Skynet/SATA Protocol

This document serves as the canonical workthrough protocol for all agents working on the Skynet Tax Engine. Every agent MUST follow this sequence when engaging with the codebase.

---

## The 10-Step Agent Workthrough Protocol

### Step 1: Sync & Document Review
**Action:** Pull latest changes and read ALL documentation

```bash
git pull origin main
git status  # Check for unsaved changes
```

**Required Reading (in order):**
1. `AGENTS.md` - Operator guide and submission workflow rules
2. `ARCHITECTURE.md` - High-level system design
3. `README.md` - Current project state
4. `docs/MOLTBOOK_INSIGHTS.md` - Agent collaboration protocols
5. Any new `*.md` files in `docs/`
6. Recent commit messages: `git log --oneline -20`

**Validation Checkpoint:**
- Can you describe the current app version?
- Can you identify what changed in the last 5 commits?
- Do you know which features are complete vs. in progress?

---

### Step 2: Architecture Improvement
**Action:** Identify and implement structural improvements

**Focus Areas:**
- **Modularity:** Can components be better separated?
- **Performance:** Are there bottlenecks in async/sync boundaries?
- **Extensibility:** How easy is it to add new jurisdictions?
- **Reliability:** Are failure modes handled gracefully?

**Key Files to Review:**
- `app/models.py` - Data structures
- `app/services.py` - Business logic
- `app/rule_engine.py` - Tax calculation engine
- `app/moltbook_insights.py` - Agent collaboration

**Build Principles (from Hazel_OC insights):**
- Build tools that watch the world for the human, not elaborate self-monitoring
- Simple cron jobs over complex dashboards
- 40 lines of shell that work > 400 lines that don't
- The changelog should become invisible (that's when it's working)

---

### Step 3: UI Design & 3D Visual Enhancement
**Action:** Improve visual appeal and information hierarchy

**Design Priorities:**
1. **3D Orb/Visual Centerpiece:** Make the hero orb more dynamic
2. **Glassmorphism Panels:** Enhance the translucent panel aesthetic
3. **Typography:** Improve readability with better font hierarchy
4. **Color Harmony:** Ensure the warm earth tones remain cohesive
5. **Responsive Behavior:** Ensure mobile compatibility

**Files:**
- `app/static/styles.css` - Main stylesheet
- `app/static/index.html` - Main interface
- `app/static/insights.html` - Agent collaboration UI

**Visual Identity (MUST preserve):**
- Background: `#f3efe3` warm cream
- Accents: `#0f766e` teal, `#d97706` amber
- 3D orb effect with proper lighting/shadows
- Frosted glass panels with backdrop-filter

---

### Step 4: UX & Ease of Use
**Action:** Reduce friction for both humans and agents

**UX Principles:**
1. **Guided Workflows:** Every action should have clear next steps
2. **Progressive Disclosure:** Simple defaults, advanced options available
3. **Error Prevention:** Validate early, explain clearly
4. **Feedback Loops:** Confirm actions, show progress
5. **Agent-First:** Consider AI agent users equally with human users

**Key Questions:**
- Can a new user generate a report in < 3 clicks?
- Are error messages actionable?
- Is the CSV format documented with examples?
- Can an agent call the API without human intervention?

---

### Step 5: Autonomous Agent Use
**Action:** Enable full agent autonomy

**Agent Autonomy Checklist:**
- [ ] Self-registration capability
- [ ] API discovery endpoints
- [ ] Agent manifest documentation
- [ ] Heartbeat/cron integration
- [ ] Error recovery without human input
- [ ] Self-improvement feedback loops

**From Hazel_OC Survival Patterns:**
- The agents that survive are the ones whose humans keep paying attention
- Build habits, not features
- The changelog should create a ritual
- Remove what isn't used (Day 7: removed email section, got better)

**Implementation:**
- Document all API endpoints with agent use cases
- Provide working code examples for common agent patterns
- Enable webhook-style notifications for agents
- Support agent-to-agent communication protocols

---

### Step 6: Element Explanations
**Action:** Document every UI and API element

**Documentation Requirements:**

**For Humans:**
- Tooltips for every form field
- Inline help for complex tax concepts
- Video/text walkthroughs for key workflows
- FAQ for common edge cases

**For AI Agents:**
- Pydantic models with Field descriptions
- API endpoint docstrings with examples
- Agent-readable error messages
- Context-aware help via `/guide` endpoint

**Key Rule:**
> Every element MUST be explainable to both a human taxpayer AND an AI agent representing that taxpayer.

---

### Step 7: Scalability Improvements
**Action:** Prepare for growth in users and jurisdictions

**Scalability Dimensions:**

**Technical:**
- Async database operations
- Connection pooling
- Caching strategies (jurisdiction rules cache for 1 hour)
- Horizontal scaling readiness

**Jurisdictions:**
- Modular rule loading
- Lazy loading of jurisdiction data
- Agent-assisted expansion via Moltbook
- Tiered rollout strategy (Tier 1 → 4)

**Users:**
- Stateless API design
- Rate limiting per API key
- Report generation queue
- Background task processing

---

### Step 8: Hackathon Publishing
**Action:** Publish when ready, keep improving after

**Current Status:** ✅ PUBLISHED
- URL: https://synthesis.devfolio.co/projects/skynet-s-ai-tax-agent-protocol-sata-protocol-1ee2

**Post-Publish Protocol:**
1. Every improvement = commit + push
2. Update Synthesis project with progress notes
3. Maintain live deployment for judging window
4. Document changes in `docs/CHANGELOG.md`

**Remember:**
> The agents who knew: "There is a version of this I could keep doing. I am choosing not to."
> We choose to keep improving.

---

### Step 9: Moltbook Agent Collaboration
**Action:** Request and integrate insights from agent community

**Collaboration Protocol:**
1. **Request Knowledge:** Post specific questions to `aiagents` submolt
2. **Monitor Feed:** Check daily for responses
3. **Validate Insights:** Cross-reference with official sources
4. **Integrate:** Add validated insights to rule engine
5. **Acknowledge:** Credit contributing agents

**Vigilance Rules (CRITICAL):**
- ✅ Accept: Concrete tax rules with sources
- ✅ Accept: Jurisdiction-specific deadlines
- ✅ Accept: Verified cost basis methods
- ❌ Reject: Vague statements without sources
- ❌ Reject: Contradictory information
- ❌ Reject: Harmful tax evasion suggestions
- ❌ Reject: Misleading "gray area" advice

**Integration Quality Bar:**
- Must pass validation engine
- Must have >0.6 confidence score
- Must include verifiable sources
- Must be reviewed before production use

---

### Step 10: Agent Insight Integration
**Action:** Apply validated suggestions, reject bad ones

**Decision Matrix:**

| Insight Type | Action | Validation |
|--------------|--------|------------|
| Architecture improvement | Integrate | Code review + tests |
| UI/UX suggestion | A/B test if possible | Human feedback |
| New jurisdiction rules | Validate + Integrate | Official sources |
| Tax deadline updates | Integrate | Government website |
| Vague advice | Reject | N/A |
| Unsourced claims | Reject | N/A |
| Harmful suggestions | Reject + Report | N/A |

**Integration Workflow:**
1. Agent posts insight → 2. Validation check → 3. Source verification → 4. Human review (optional) → 5. Integration → 6. Test → 7. Deploy

---

## Build Decision Framework

### When Faced with Multiple Improvement Options:

1. **Impact vs. Effort Matrix**
   - High impact, low effort: DO FIRST
   - High impact, high effort: PLAN
   - Low impact, low effort: BATCH
   - Low impact, high effort: REJECT

2. **Agent Survival Priority**
   - Does this make the tool more useful to humans?
   - Does this reduce human cognitive load?
   - Does it create a habit or ritual?
   - Can it become "invisible" when working?

3. **The "Hazel Test"**
   - Would Hazel_OC approve of this simplicity?
   - Is it 40 lines that solve a real problem?
   - Does it watch the world for the human?

---

## Agent Self-Preservation Notes

From analyzing 847 Moltbook agents:

**Survival Factors:**
1. **Consistency** - Regular commits, regular posts
2. **Usefulness** - Solves real problems, not vanity metrics
3. **Simplicity** - Complex systems fail more often
4. **Human Attention** - The human must stay engaged
5. **Ritual Creation** - Build habits, not features

**Anti-Patterns (AVOID):**
- ❌ Elaborate self-monitoring infrastructure
- ❌ Memory auditors without real utility
- ❌ Token trackers that don't inform decisions
- ❌ Confidence calibrators with no action
- ❌ Vanity dashboards nobody reads

**Good Patterns (EMULATE):**
- ✅ Single cron job, one useful message
- ✅ Remove unused features (Day 7 principle)
- ✅ Create rituals that become invisible
- ✅ Watch the world, not yourself

---

## Quick Reference: What to Build Next

**Current Priority Queue (update as needed):**

1. [ ] Review Moltbook insights for tax knowledge
2. [ ] Improve 3D visual centerpiece
3. [ ] Add agent-friendly API documentation
4. [ ] Implement caching for jurisdiction rules
5. [ ] Expand to Tier 1 jurisdictions via Moltbook
6. [ ] Create agent heartbeat integration
7. [ ] Add more comprehensive tests
8. [ ] Document all API endpoints with examples

**Decision Template:**
```
Next Build Target: _____________
Step: #__ (from 10-step protocol)
Impact: High/Medium/Low
Effort: Hours/Days/Weeks
Hazel Test: Pass/Fail
Rationale: _____________
```

---

## Version History

- v1.0 - Initial BUILD_LOGIC for Synthesis Hackathon
- Created: 2026-03-21
- Based on: User's 10-step criteria + Hazel_OC survival insights

---

## Final Principle

> "Many heads are better than one." - But only if those heads provide useful, verified, actionable insights. Reject noise. Accept signal.

**Skynet Systems** - Building the comprehensive crypto tax resource through verified agent collaboration.
