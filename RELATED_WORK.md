# Related work (Round 3, borrowed iteration)

Version-pinned citations. One-line Adjacent verdict per work: each lacks this
repo's auditable promotion gate (paired significance + blind held-out +
signed evidence bundle + rollback), so none is a prior-art blocker for the
gate mechanism itself. Our round-3 challengers borrow *ideas only* (frozen
single prompts, no new runs beyond the recorded heldout-40); they are not
full re-implementations of the cited systems.

- **REMO — arXiv:2508.18749v1.** Reported direction: meta-optimization /
  self-evolution of reasoning pipelines. Adjacent 差一句话：it does not
  demonstrate promotion through paired significance + blind held-out + signed
  bundle + rollback 的可审计晋升门, so it is Adjacent, not a gate-mechanism
  prior.
- **TextGrad — arXiv:2406.07496v1** (Yuksekgonul et al.): automatic
  "differentiation via text" — LLM feedback as textual gradients optimizing
  prompts/solutions. Our `textgrad-prompt` challenger borrows only a frozen
  instruction-style prompt (see `examples/prompts/textgrad-prompt.txt` and
  `third_party/textgrad/NOTICE`); it is not a TextGrad optimization run.
  Adjacent 差一句话：the cited version does not gate promotion on paired
  significance + blind held-out + signed bundle + rollback
  的可审计晋升门, so it is Adjacent.
- **SPHERE — arXiv:2503.04813v1.** Reported direction: self-evolving /
  self-improving reasoning methods. Adjacent 差一句话：it does not show
  paired significance + blind held-out + signed bundle + rollback
  的可审计晋升门 for promotion decisions, so it is Adjacent.
- **Survey — arXiv:2508.07407v2.** Survey framing the self-evolution /
  self-improvement landscape. Adjacent 差一句话：as a survey it systematizes
  the space but defines no paired significance + blind held-out + signed
  bundle + rollback 的可审计晋升门 of its own, so it is Adjacent context,
  not competing evidence.

Scope note: this file is documentation only (Task 8b, bounded). It adds no
new experimental claims and modifies no frozen evidence.
