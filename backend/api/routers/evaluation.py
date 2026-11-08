from datetime import datetime, timezone
import json
from fastapi import APIRouter, HTTPException
from backend.evaluation import EvaluationExample, evaluate, seed_examples
from backend.storage import database

router = APIRouter(prefix='/evaluation', tags=['Evaluation'])


def all_examples():
    examples = {e.example_id: e for e in seed_examples()}
    with database() as connection:
        for row in connection.execute('SELECT payload FROM evaluation_examples'):
            example = EvaluationExample(**json.loads(row['payload']))
            examples[example.example_id] = example
    return list(examples.values())


@router.get('/examples')
def examples():
    return all_examples()


@router.put('/examples/{example_id}')
def save_example(example_id: str, example: EvaluationExample):
    if example.example_id != example_id:
        raise HTTPException(422, 'Example ID in the URL must match the example.')
    # Reviewer attribution is supplied explicitly by the person using the app.
    example.reviewed_at = datetime.now(timezone.utc).isoformat() if example.reviewer.strip() else None
    with database() as connection:
        connection.execute('INSERT INTO evaluation_examples VALUES (?, ?) ON CONFLICT(example_id) DO UPDATE SET payload=excluded.payload',
                           (example_id, example.model_dump_json()))
    return example


@router.get('/run')
def run(include_drafts: bool = False):
    return evaluate(all_examples(), include_drafts)
