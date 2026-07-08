# canitplaydoom-harness

Reference harness for the **[Can It Play DOOM?](https://github.com/triple-it)** AI game benchmark.

It runs a ViZDoom benchmark driven by any OpenAI-compatible model (local via
**Ollama** or cloud via **OpenRouter**) and produces a verifiable result
bundle (deterministic demo + logs + manifest + hash) plus an mp4.

See the specification in `HARNESS-SPEC.md` (mirrored from the project DOCS).

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

ViZDoom needs SDL2/build tools on some platforms. The canonical benchmark host
is an x86_64 + CUDA machine (e.g. Olares One). Pure-Python logic (scoring,
encoding, agent parsing) is testable without the engine.

## Usage

Run a local model (free):

```bash
canitplaydoom run \
  --scenario defend_the_center --modality ascii \
  --base-url http://localhost:11434/v1 --model qwen2.5:14b-instruct \
  --episodes 5 --max-steps 500 --seed 12345 --out bundles/qwen14b
```

Run a cloud model (OpenRouter):

```bash
export OPENROUTER_API_KEY="sk-or-…"
canitplaydoom run \
  --scenario defend_the_center --modality ascii \
  --base-url https://openrouter.ai/api/v1 --model openai/gpt-4o-mini \
  --api-key-env OPENROUTER_API_KEY \
  --episodes 5 --max-steps 500 --seed 12345 --out bundles/gpt4o-mini
```

Verify and package for submission:

```bash
canitplaydoom verify bundles/qwen14b
canitplaydoom package bundles/qwen14b --author your-github --video-url "https://youtube.com/watch?v=…"
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
