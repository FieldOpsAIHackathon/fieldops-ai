# FieldOps: Hackathon Judge Q&A

Repository-grounded answers to likely technical judging questions. Be clear about what is
synthetic, what has been demonstrated, and what remains unvalidated. Do not claim RAG,
embeddings, field accuracy, or agronomic validation.

## Model training, fine-tuning, and data

### 1. Did you train, fine-tune, or prompt-engineer foundation models?

We fine-tuned a YOLO26s detector on synthetic sticky-trap images, including phone-style versions.
We did not fine-tune the language model: Qwen3.6-35B-A3B (NVFP4) runs locally on the GB10 and is
prompted to phrase or explain facts from FieldOps. Spray decisions are made by deterministic Python,
not by either model.

### 2. What did your training or reference dataset look like?

The detector was trained on 3,000 synthetic cards and fine-tuned with 2,000 phone-style versions.
We tested it on 200 phone-style synthetic images generated from seeds not used for training or
validation. We also have six annotated synthetic reference cards and a committed synthetic season
for replay. We have not trained on real trap photos or curated an operational-manual corpus.

### 3. How do you prevent hallucinations when accuracy matters?

The LLM does not make treatment decisions. Python computes biofix and degree-days using configured
thresholds. For SMS alerts, model-generated text is accepted only when its numbers and date words
appear in the supplied facts; otherwise, a deterministic template is used. General Q&A is prompted
to use supplied facts, but does not have the same output checks, so it is explanatory, not
authoritative. The thresholds are demo values, not agronomic advice.

### 4. How did you evaluate model performance?

For vision, we compared predicted counts with exact synthetic ground truth. On 200 held-out-seed
phone-style images, codling moth counts were exact on 189/200, with a mean absolute error (MAE) of
0.07; oriental fruit moth counts were exact on 192/200, with an MAE of 0.04. We also scored six
synthetic reference cards. These are synthetic-data results, not field validation. The decision
engine has hand-checked assertions for degree-day calculations, biofix, and spray-window
transitions.

## Architecture and data pipeline

### 5. How are embeddings and vectors managed?

We do not use embeddings, a vector database, or RAG. The agent calls tools backed by local season
data and the deterministic decision engine.

### 6. How do you validate structured outputs from the LLM?

The LLM returns prose; its output is not used as a structured input to the decision engine. Counts
and replay timelines are structured data produced by application code and checked against their
contracts. Alert prose has factual-number and date-word checks with a template fallback. We do not
use Pydantic, function-calling schemas, or LLM validation retries.

### 7. What is your end-to-end latency budget and bottleneck?

We have not established a measured latency budget or profiled each stage. The vision documentation
describes a phone-photo reply in a few seconds, with much of that time in the agent turn. The API
allows up to 60 seconds for the vision request, and the local LLM request has a 30-second timeout.
We would measure these on the demo hardware before quoting a precise latency. The dashboard trigger
returns immediately and delivers the alert asynchronously.

### 8. How does it work offline or with poor connectivity?

The committed season replay, dashboard, vision inference, local language model, and decision logic
can run locally. Telegram photo transport and phone-message delivery require connectivity; a phone
alert cannot be delivered after the network is disconnected. We do not currently claim queued
offline delivery or cloud fallback.

## UX, human review, and system design

### 9. What is the human-in-the-loop flow when model confidence is low?

We do not yet have a calibrated low-confidence workflow or a UI that asks a grower to confirm an
uncertain count. The detector uses a fixed confidence threshold and returns counts with an annotated
image. If the vision service is unavailable, the caller can report that rather than guess. Review
and correction of uncertain counts on real photos is a next step.

### 10. How do you manage large context windows?

We do not send large document collections or operational logs to the model. The agent assembles a
compact status and recent-count context from local tools, and prompts limit answer length. There is
no document chunking, reranking, or sliding-window summarization.

### 11. How do you handle security and proprietary data?

Inference and season data are local. The API binds to loopback and the OpenShell sandbox bridge, not
the venue network; the sandbox has a tool policy, and browser-origin checks restrict alert and photo
endpoints. We do not claim multi-user role-based access control or encryption-at-rest guarantees.
When Telegram delivery is used, messages go through Telegram's service.

## Viability and scope

### 12. What is mock data versus a live-integrated pipeline?

The season replay is committed synthetic data, not live farm telemetry. The detector is a working
local inference path for trap photos, and the repository documents a demonstrated Telegram photo
count workflow. The 3D drone survey is simulated, not physical drone integration. The pitch film is
recorded, not a live connection. Field accuracy and grower outcomes have not been validated.

### 13. What would you prioritize with two more weeks?

First, evaluate and improve the detector using real trap photos labeled against ground truth, with a
clear review path for uncertain counts. Second, validate the decision workflow and thresholds with
growers and domain experts. Measure errors and usability before expanding to more species.

### 14. How do API costs scale as query volume increases tenfold?

There is no per-query hosted-model API cost in the inference path: the language model and detector
run locally. We have not quantified hardware, power, or operating costs at higher volume. Telegram
transport still depends on its service. At higher volumes, we would benchmark local capacity rather
than claim an unmeasured cost curve.

### 15. Why use generative AI instead of deterministic rules or search?

We do not use generative AI for decisions that can be expressed as rules. Python is more
deterministic and auditable for biofix, degree-day accumulation, and threshold checks. The local
language model turns those results into concise explanations and answers grower questions; it does
not decide whether to spray.

### 16. How do the biofix thresholds and degree-day tracking work?

Imagine the grower checking a sticky trap in one orchard block. One moth—or a one-day spike—gets
noticed, but it doesn't start the treatment clock. When the trap shows at least two codling moths on
two consecutive daily checks, FieldOps marks biofix: that's the signal to start tracking conditions.
Then it uses temperature-based degree-days—not just the bug count—to identify when the demo's spray
window opens at 250 degree-days. So the short version is: two moths, two days to start the clock; the
temperature timeline determines the response window. Those are demo thresholds, not spraying advice.

## Evidence in this repository

- [Detector training and evaluation](fieldops/yolo/README.md)
- [Detector model card](models/README.md)
- [Decision rules and timeline contract](dashboard/TIMELINE_CONTRACT.md)
- [System boundaries and offline behavior](ORCHESTRATION.md)
- [Presenter runbook and claim boundaries](pitch/DEMO.md)
- [Judge-facing evidence snapshot](pitch/evidence.json)
