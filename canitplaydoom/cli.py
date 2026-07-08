"""Command-line interface for the Can It Play DOOM? harness."""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_run(args: argparse.Namespace) -> int:
    from .agent import Agent
    from .runner import run_benchmark

    provider = "ollama" if "11434" in args.base_url else "openrouter"
    agent = Agent(
        model=args.model,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
        temperature=args.temperature,
        max_tokens_per_step=args.max_tokens_per_step,
    )
    manifest = run_benchmark(
        scenario_name=args.scenario,
        agent=agent,
        episodes=args.episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        out_dir=args.out,
        model_meta={"name": args.model, "provider": provider, "params": None},
        modality=args.modality,
        render_video=not args.no_video,
    )
    print(json.dumps(manifest["scores"], indent=2))
    print(f"Bundle written to: {args.out}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from .verify import verify_bundle

    report = verify_bundle(args.bundle, tolerance=args.tolerance)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


def _cmd_package(args: argparse.Namespace) -> int:
    from .package import package_submission

    disclosure = None
    if args.disclosure:
        disclosure = json.loads(args.disclosure)
    dest = package_submission(
        bundle_dir=args.bundle,
        video_url=args.video_url,
        author=args.author,
        disclosure=disclosure,
        data_root=args.data_root,
    )
    print(f"Submission written to: {dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="canitplaydoom", description="Can It Play DOOM? harness")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a benchmark and produce a bundle")
    run.add_argument("--scenario", default="defend_the_center")
    run.add_argument("--modality", default="ascii", choices=["ascii"])
    run.add_argument("--base-url", default="http://localhost:11434/v1")
    run.add_argument("--model", required=True)
    run.add_argument("--api-key-env", default=None)
    run.add_argument("--temperature", type=float, default=0.2)
    run.add_argument("--episodes", type=int, default=5)
    run.add_argument("--max-steps", type=int, default=500)
    run.add_argument("--max-tokens-per-step", type=int, default=64)
    run.add_argument("--seed", type=int, default=12345)
    run.add_argument("--out", required=True)
    run.add_argument("--no-video", action="store_true")
    run.set_defaults(func=_cmd_run)

    verify = sub.add_parser("verify", help="Replay a bundle and recompute scores")
    verify.add_argument("bundle")
    verify.add_argument("--tolerance", type=float, default=1.0)
    verify.set_defaults(func=_cmd_verify)

    package = sub.add_parser("package", help="Package a bundle into a data submission")
    package.add_argument("bundle")
    package.add_argument("--video-url", required=True)
    package.add_argument("--author", required=True)
    package.add_argument("--disclosure", default=None, help="JSON string")
    package.add_argument("--data-root", default="data")
    package.set_defaults(func=_cmd_package)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)
