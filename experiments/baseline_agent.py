"""Frozen v1 baseline: original loop/prompt, with the source gate disabled."""
from experiments.previous_agent import _run_agent


def run_agent(question, provider, tools, max_steps=6):
    return _run_agent(question, provider, tools, max_steps, validate_sources=False)
