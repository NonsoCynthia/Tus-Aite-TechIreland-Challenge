"""Same seed, byte-identical output.

Every downstream guarantee rests on this: that a published tag means one specific
dataset, that the sample is reproducible, that a past ranking can be replayed.

Run at BOTH profiles. Unstable iteration order and unseeded randomness surface at
scale, not on a few hundred rows.
"""
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def digest():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob("*.csv"))}


def generate(profile):
    subprocess.run(
        ["python", "-m", "generator.generate", "--profile", profile],
        cwd=ROOT, check=True, capture_output=True)


@pytest.mark.parametrize("profile", ["small", "full"])
def test_generation_is_byte_identical(profile):
    generate(profile)
    first = digest()
    assert first, "generator produced no CSVs"

    shutil.rmtree(OUT, ignore_errors=True)
    generate(profile)
    second = digest()

    assert set(first) == set(second), "different files produced across runs"
    differing = [n for n in first if first[n] != second[n]]
    assert not differing, (
        f"[{profile}] these files differ between two runs of the same seed: {differing}. "
        f"Check for unordered iteration, an unseeded RNG, or datetime.now() in output.")
