from collections import defaultdict, deque

from tcu.models.dependency_graph import DependencyGraph
from tcu.dependency_policy import DependencyPolicyResolver


class DependencyGraphBuilder:
    """
    Builds a Directed Acyclic Graph (DAG) representing
    ECU update dependencies.
    """

    def build(self, eligible_ecus, campaign=None):

        graph = DependencyGraph()
        policy_resolver = DependencyPolicyResolver()
        ecus = self._normalize_ecu_collection(eligible_ecus)
        dependency_overrides = getattr(campaign, "dependency_overrides", {}) or {}

        # Add every ECU as a node
        for ecu in ecus:
            graph.add_node(ecu.ecu_name)

        # Build dependency edges
        #
        # dependency ---> ecu
        #
        # Gateway ---> BCM
        # BCM -----> Cluster
        #
        for ecu in ecus:

            if ecu.ecu_name in dependency_overrides:
                dependencies = list(dependency_overrides[ecu.ecu_name])
            else:
                dependencies = policy_resolver.for_ecu(ecu.ecu_name).dependencies

            if not dependencies and ecu.ecu_name not in dependency_overrides:
                dependencies = ecu.dependencies

            for dependency in dependencies:

                graph.add_dependency(
                    dependency,
                    ecu.ecu_name
                )

        return graph

    def validate_campaign_dependencies(self, eligible_ecus, campaign=None):
        dependency_overrides = getattr(campaign, "dependency_overrides", {}) or {}
        if not dependency_overrides:
            return []

        ecus = self._normalize_ecu_collection(eligible_ecus)
        eligible_names = {ecu.ecu_name for ecu in ecus}
        known_names = set(DependencyPolicyResolver().topology.ecu_registry())
        known_names.update(eligible_names)
        errors = []

        for ecu_name, dependencies in dependency_overrides.items():
            if ecu_name not in known_names:
                errors.append(f"dependency override targets unknown ECU: {ecu_name}")
            for dependency in dependencies:
                if dependency not in known_names:
                    errors.append(
                        f"{ecu_name} depends on unknown ECU: {dependency}"
                    )

        if errors:
            return errors

        try:
            TopologicalUpdatePlanner().plan(self.build(eligible_ecus, campaign=campaign))
        except RuntimeError as exc:
            errors.append(str(exc))

        return errors

    @staticmethod
    def _normalize_ecu_collection(eligible_ecus):
        if hasattr(eligible_ecus, "get_all_ecus"):
            return eligible_ecus.get_all_ecus()
        return list(eligible_ecus)


class TopologicalUpdatePlanner:

    def plan(self, graph: DependencyGraph, priority=None):
        priority = priority or {}

        indegree = defaultdict(int)

        # Initialize indegree
        for node in graph.nodes:
            indegree[node] = 0

        # Compute indegree
        for parent in graph.graph:

            for child in graph.graph[parent]:

                indegree[child] += 1

        # Queue all root nodes
        queue = deque()

        for node in self._sort_nodes(graph.nodes, priority):

            if indegree[node] == 0:
                queue.append(node)

        update_order = []

        while queue:

            node = queue.popleft()

            update_order.append(node)

            for child in self._sort_nodes(graph.children(node), priority):

                indegree[child] -= 1

                if indegree[child] == 0:
                    queue.append(child)

        # Cycle detection
        if len(update_order) != len(graph.nodes):

            raise RuntimeError(
                "Dependency cycle detected. Update plan cannot be generated."
            )

        return update_order

    @staticmethod
    def _sort_nodes(nodes, priority):
        return sorted(nodes, key=lambda node: (priority.get(node, 9999), node))

    def print_update_order(self, update_order):

        print()
        print("=" * 50)
        print("TOPOLOGICAL UPDATE PLAN")
        print("=" * 50)

        for index, ecu in enumerate(update_order, start=1):

            print(f"{index}. {ecu}")

        print()
