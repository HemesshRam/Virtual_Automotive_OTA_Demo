from collections import defaultdict


class DependencyGraph:
    """
    Directed graph representing ECU update dependencies.
    """

    def __init__(self):

        self.graph = defaultdict(list)

        self.nodes = set()

    def add_node(self, ecu_name):

        self.nodes.add(ecu_name)

    def add_dependency(self, parent, child):
        """
        parent -> child

        Parent must finish updating before child.
        """

        self.nodes.add(parent)
        self.nodes.add(child)

        self.graph[parent].append(child)

    def children(self, node):

        return self.graph.get(node, [])

    def print_graph(self):

        print()
        print("=" * 50)
        print("DEPENDENCY GRAPH")
        print("=" * 50)

        for node in sorted(self.nodes):

            children = sorted(self.graph.get(node, []))

            if children:

                print(node)

                for child in children:

                    print(f"   └──► {child}")

            else:

                print(node)

        print()
