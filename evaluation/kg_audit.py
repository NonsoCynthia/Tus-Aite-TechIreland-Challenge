"""Knowledge-graph audit checks for the triage agent system.

These checks validate repository artefacts that make the KG-backed agent
architecture auditable: RDF assets parse, decision-layer ontology terms exist,
SHACL covers agent output classes, citation-role mappings are consistent, and
the held-out answer key is absent from graph-building assets.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef

EAT = Namespace("https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#")
SH = Namespace("http://www.w3.org/ns/shacl#")

EXPECTED_ROLE_SUBPROPERTIES = {
    "urgency": "citesUrgencyEvidence",
    "capacity": "citesCapacityEvidence",
    "timeframe": "citesTimeframeEvidence",
    "multi_list": "citesMultiListEvidence",
}
EXPECTED_COORDINATOR_EVIDENCE_TYPES = {
    "urgency": ("score",),
    "timeframe": ("referral_state", "rule"),
    "capacity": ("bed_status",),
}
FORBIDDEN_ANSWER_KEY_TOKENS = (
    "eval.ground_truth",
    "ground_truth",
    "latent_hazard",
    "deterioration_date",
    "deterioration_type",
)


@dataclass(frozen=True)
class KGAuditCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class KGAuditReport:
    checks: tuple[KGAuditCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [asdict(check) for check in self.checks],
        }

    def render_text(self) -> str:
        lines = [
            "Knowledge Graph Audit",
            f"Result: {'PASS' if self.passed else 'FAIL'} "
            f"({self.passed_count}/{len(self.checks)} checks passed)",
            "",
        ]
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"[{status}] {check.name}")
            lines.append(f"  {check.detail}")
        return "\n".join(lines)


def run_audit(root: Path | None = None) -> KGAuditReport:
    project_root = root or Path(__file__).resolve().parents[1]
    checks = [
        _check("RDF assets parse", lambda: _assert_rdf_assets_parse(project_root)),
        _check("held-out answer key absent from KG assets", lambda: _assert_no_answer_key(project_root)),
        _check("decision ontology terms exist", lambda: _assert_decision_terms(project_root)),
        _check("SHACL covers agent output classes", lambda: _assert_decision_shapes(project_root)),
        _check("citation role mappings are consistent", lambda: _assert_citation_roles(project_root)),
    ]
    return KGAuditReport(tuple(checks))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit KG, SHACL and citation artefacts that support agent explainability."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_audit()
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


def _check(name: str, assertion: Callable[[], str]) -> KGAuditCheck:
    try:
        detail = assertion()
    except AssertionError as exc:
        return KGAuditCheck(name=name, passed=False, detail=str(exc))
    except Exception as exc:  # pragma: no cover - surfaced in CLI output.
        return KGAuditCheck(name=name, passed=False, detail=f"{type(exc).__name__}: {exc}")
    return KGAuditCheck(name=name, passed=True, detail=detail)


def _assert_rdf_assets_parse(root: Path) -> str:
    ttl_files = [
        root / "kg" / "ontology" / "eat.ttl",
        root / "kg" / "shapes" / "structural.ttl",
        *sorted((root / "kg" / "mappings").glob("*.ttl")),
    ]
    parsed = 0
    for path in ttl_files:
        graph = Graph()
        graph.parse(path, format="turtle")
        parsed += 1
    return f"parsed {parsed} Turtle files"


def _assert_no_answer_key(root: Path) -> str:
    checked_files = [
        root / "kg" / "ontology" / "eat.ttl",
        root / "kg" / "shapes" / "structural.ttl",
        *sorted((root / "kg" / "mappings").glob("*.ttl")),
        *sorted((root / "kg" / "queries").glob("*.rq")),
    ]
    violations: list[str] = []
    for path in checked_files:
        text = path.read_text(encoding="utf-8")
        found = [token for token in FORBIDDEN_ANSWER_KEY_TOKENS if token in text]
        if found:
            violations.append(f"{path.relative_to(root)}: {', '.join(found)}")
    assert not violations, "; ".join(violations)
    return f"checked {len(checked_files)} KG assets"


def _assert_decision_terms(root: Path) -> str:
    ontology = _parse_turtle(root / "kg" / "ontology" / "eat.ttl")
    required_classes = ("Score", "Decision", "RankedPlacement", "RuleCheck")
    missing_classes = [
        name for name in required_classes if (EAT[name], RDF.type, OWL.Class) not in ontology
    ]
    assert not missing_classes, f"missing classes: {missing_classes}"

    required_subproperties = tuple(EXPECTED_ROLE_SUBPROPERTIES.values())
    missing_subproperties = [
        name
        for name in required_subproperties
        if (EAT[name], RDFS.subPropertyOf, EAT.cites) not in ontology
    ]
    assert not missing_subproperties, f"missing cites subproperties: {missing_subproperties}"
    assert (EAT.cites, RDFS.subPropertyOf, URIRef("http://www.w3.org/ns/prov#used")) in ontology
    return "Score, Decision, RankedPlacement, RuleCheck and cites subproperties present"


def _assert_decision_shapes(root: Path) -> str:
    shapes = _parse_turtle(root / "kg" / "shapes" / "structural.ttl")
    required_targets = ("Score", "Decision", "RankedPlacement", "RuleCheck")
    missing_targets = [
        name for name in required_targets if (None, SH.targetClass, EAT[name]) not in shapes
    ]
    assert not missing_targets, f"missing SHACL targetClass shapes: {missing_targets}"

    score_shapes = set(shapes.subjects(SH.targetClass, EAT.Score))
    assert any((shape, SH.property, None) in shapes for shape in score_shapes)
    return "decision-layer output classes have SHACL targetClass coverage"


def _assert_citation_roles(root: Path) -> str:
    graph_roles = _literal_assignment(
        root / "retrieval" / "app" / "graph.py", "_ROLE_SUBPROPERTY"
    )
    read_roles = _literal_assignment(root / "retrieval" / "app" / "reads.py", "_ROLE_SUBPROPERTY")
    coordinator_types = _literal_assignment(
        root / "coordinator" / "app" / "citations.py", "ROLE_EVIDENCE_TYPES"
    )

    assert graph_roles == EXPECTED_ROLE_SUBPROPERTIES, graph_roles
    assert read_roles == EXPECTED_ROLE_SUBPROPERTIES, read_roles
    assert coordinator_types == EXPECTED_COORDINATOR_EVIDENCE_TYPES, coordinator_types
    return "retrieval graph/read role maps and coordinator evidence types agree"


def _parse_turtle(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    return graph


def _literal_assignment(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and node.value is not None:
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


if __name__ == "__main__":
    raise SystemExit(main())
