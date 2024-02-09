from pathlib import Path

from bystro.cli.tests.test_cli import EXAMPLE_CACHED_AUTH
from bystro.api.proteomics import upload_proteomics_dataset
from bystro.cli.cli import authenticate
from msgspec import json as mjson


def test_upload_proteomics_dataset(mocker):
    mocker.patch(
        "bystro.cli.cli.authenticate",
        return_value=(
            EXAMPLE_CACHED_AUTH,
            "localhost:8080",
        ),
    )

    mock_response = '{"success": true}'
    mocker.patch(
        "requests.post",
        return_value=mocker.Mock(
            status_code=200, json=lambda: mjson.decode(mock_response), text=mock_response
        ),
    )

    protein_abundance_filename = str(Path(__file__).parent / "protein_abundance_file.tsv")
    experiment_annotation_filename = str(Path(__file__).parent / "experiment_annotation_file.tsv")

    response = upload_proteomics_dataset(
        protein_abundance_file=protein_abundance_filename,
        experiment_annotation_file=experiment_annotation_filename,
        annotation_job_id="123",
    )

    assert response == {}
