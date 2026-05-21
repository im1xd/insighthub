"""
تحليل شبكة التفاعلات.

نبني graph من الـ mentions: كل ذكر (@user) في منشور
هو حافة من المؤلف إلى الـ user المذكور.

عند غياب user_id في الـ posts، نستخدم mentions فقط
لبناء شبكة مذكوريَة (mentioned-by-mentioned).

نُرجع تنسيقاً مطابقاً لـ schema الـ Frontend:
  nodes: [{id, handle, size, group}]
  edges: [{source, target, weight}]
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List

from loguru import logger


def build_interaction_network(
    posts: List[Dict[str, Any]],
    max_nodes: int = 50,
    max_edges: int = 200,
) -> Dict[str, Any]:
    if not posts:
        return {"nodes": [], "edges": [], "metrics": {}}

    edge_weights: Counter = Counter()
    node_activity: Counter = Counter()

    for p in posts:
        author = p.get("user_handle") or p.get("user_id")
        author = str(author).lstrip("@").lower() if author else None
        mentions = [str(m).lstrip("@").lower() for m in (p.get("mentions") or [])]

        if author:
            node_activity[author] += 1

        for m in mentions:
            if not m:
                continue
            node_activity[m] += 1
            if author and m != author:
                edge_weights[(author, m)] += 1
            elif not author:
                # إذا لا نعرف المؤلف، نربط الـ mentions ببعضها (co-occurrence)
                for other in mentions:
                    if other != m and other:
                        key = tuple(sorted([m, other]))
                        edge_weights[key] += 1

    if not node_activity:
        return {"nodes": [], "edges": [], "metrics": {}}

    # نأخذ أعلى max_nodes نشاطاً
    top_nodes = dict(node_activity.most_common(max_nodes))
    top_set = set(top_nodes.keys())

    # نُرتّب الحواف ونُبقي فقط ما يصل بين العقد المختارة
    filtered_edges = [
        (s, t, w) for (s, t), w in edge_weights.items()
        if s in top_set and t in top_set
    ]
    filtered_edges.sort(key=lambda x: x[2], reverse=True)
    filtered_edges = filtered_edges[:max_edges]

    # تجميع للـ degree
    degree: Counter = Counter()
    for s, t, w in filtered_edges:
        degree[s] += w
        degree[t] += w

    max_size = max(top_nodes.values()) or 1

    nodes_list: List[Dict[str, Any]] = []
    handle_to_id: Dict[str, str] = {}
    for i, (handle, count) in enumerate(top_nodes.items()):
        node_id = str(i + 1)
        handle_to_id[handle] = node_id
        size_norm = max(1, int(round(5.0 * count / max_size)))
        group = "influencer" if degree.get(handle, 0) >= 5 else "user"
        nodes_list.append({
            "id": node_id,
            "handle": f"@{handle}",
            "size": size_norm,
            "group": group,
        })

    edges_list = [
        {
            "source": handle_to_id[s],
            "target": handle_to_id[t],
            "weight": int(w),
        }
        for s, t, w in filtered_edges
    ]

    metrics = _compute_metrics(nodes_list, edges_list)
    return {"nodes": nodes_list, "edges": edges_list, "metrics": metrics}


def _compute_metrics(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, float]:
    """مقاييس networkx بسيطة."""
    if not nodes or not edges:
        return {"density": 0.0, "avg_clustering": 0.0, "components": 0}
    try:
        import networkx as nx
    except ImportError:
        return {}
    g = nx.Graph()
    for n in nodes:
        g.add_node(n["id"])
    for e in edges:
        if g.has_edge(e["source"], e["target"]):
            g[e["source"]][e["target"]]["weight"] += e["weight"]
        else:
            g.add_edge(e["source"], e["target"], weight=e["weight"])
    try:
        return {
            "density": round(nx.density(g), 4),
            "avg_clustering": round(nx.average_clustering(g), 4),
            "components": nx.number_connected_components(g),
        }
    except Exception as e:
        logger.warning(f"[network] metrics failed: {e}")
        return {}
