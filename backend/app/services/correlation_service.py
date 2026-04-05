from __future__ import annotations

from collections import Counter, defaultdict

from app.schemas import Finding, Hotspot, IssueCluster


class CorrelationService:
    def build_clusters(self, findings: list[Finding]) -> list[IssueCluster]:
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            grouped[finding.rule_id].append(finding)

        clusters: list[IssueCluster] = []
        for rule_id, items in grouped.items():
            if len(items) < 2:
                continue
            common_fix = Counter(item.fix_patch for item in items if item.fix_patch).most_common(1)
            impact_level = Counter(item.impact_level for item in items).most_common(1)
            clusters.append(
                IssueCluster(
                    cluster_id=f"cluster-{rule_id}",
                    type=rule_id,
                    count=len(items),
                    reason=f"Repeated {rule_id} pattern across {len({item.file_path for item in items})} files",
                    common_fix=common_fix[0][0] if common_fix else "",
                    impact_level=impact_level[0][0] if impact_level else "medium",
                    issue_ids=[item.id for item in items],
                    affected_files=sorted({item.file_path for item in items}),
                    affected_symbols=sorted({item.symbol_name for item in items if item.symbol_name}),
                )
            )
        return sorted(clusters, key=lambda cluster: len(cluster.issue_ids), reverse=True)

    def compute_hotspots(self, findings: list[Finding]) -> list[Hotspot]:
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for finding in findings:
            grouped[finding.file_path].append(finding)

        hotspots: list[Hotspot] = []
        for file_path, items in grouped.items():
            severity_distribution: dict[str, int] = defaultdict(int)
            for item in items:
                severity_distribution[item.severity] += 1
            hotspots.append(
                Hotspot(
                    file_path=file_path,
                    issue_count=len(items),
                    severity_distribution=dict(sorted(severity_distribution.items())),
                )
            )
        return sorted(hotspots, key=lambda hotspot: hotspot.issue_count, reverse=True)[:10]
