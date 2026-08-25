from regulatory_engine.classification.classifier import (
    select_candidate,
)
from regulatory_engine.classification.retrieval import (
    retrieve_candidates,
)


def search_and_classify(
    product,
    limit=5,
):
    candidates = retrieve_candidates(
        product,
        limit=limit,
    )

    classification = select_candidate(
        product,
        candidates,
    )

    return {
        "candidates": candidates,
        "classification": classification,
    }