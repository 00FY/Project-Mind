"""Relationship extraction for ProjectMind code intelligence."""

from projectmind.code_intelligence.models import (
    CodeEntity,
    CodeRelationship,
    RelationshipType,
)


class RelationshipExtractor:
    """Build relationships between extracted code entities."""

    def extract(
        self,
        entities: list[CodeEntity],
    ) -> list[CodeRelationship]:
        """Extract relationships from a collection of code entities."""
        relationships: list[CodeRelationship] = []

        relationships.extend(self._extract_contains(entities))

        return relationships

    @staticmethod
    def _extract_contains(
        entities: list[CodeEntity],
    ) -> list[CodeRelationship]:
        """Create contains relationships between classes and their methods."""
        relationships: list[CodeRelationship] = []

        classes = [entity for entity in entities if entity.type.value == "class"]

        methods = [entity for entity in entities if entity.type.value == "method"]

        for method in methods:
            containing_classes = [
                class_entity
                for class_entity in classes
                if (
                    class_entity.file == method.file
                    and class_entity.line_start <= method.line_start
                    and class_entity.line_end >= method.line_end
                )
            ]

            if not containing_classes:
                continue

            containing_class = min(
                containing_classes,
                key=lambda entity: entity.line_end - entity.line_start,
            )

            relationships.append(
                CodeRelationship(
                    source_entity_id=containing_class.entity_id,
                    target_entity_id=method.entity_id,
                    relationship_type=RelationshipType.CONTAINS,
                )
            )

        return relationships
