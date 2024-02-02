"""Provide a CLI for proteomics analysis."""
import argparse
from pathlib import Path
from typing import Any, BinaryIO

import requests
from bystro.api.cli import DEFAULT_DIR, authenticate, login
from msgspec import json as mjson
from enum import Enum
import json

# ruff: noqa: T201

UPLOAD_PROTEIN_ENDPOINT = "/api/jobs/proteomics/"
GET_ANNOTATION = "/api/jobs/:id"
HTTP_STATUS_OK = 200
ONE_HOUR_IN_SECONDS = 60 * 60


def _package_filename(filename: str) -> tuple[str, tuple[str, BinaryIO, str]]:
    """Wrap filename in a container suitable for upload through the requests library."""
    filepath = Path(filename)
    return (
        "file",
        (
            filepath.name,
            filepath.open("rb"),
            "application/octet-stream",
        ),
    )


class DatasetTypes(Enum):
    fragpipe_TMT = "fragpipe-TMT"
    somascan = "somascan"


def upload_proteomics_dataset(
    protein_abundance_file: str,
    experiment_annotation_file: str = None,
    annotation_job_id: str = None,
    proteomics_dataset_type: str = "fragpipe_TMT",
    user_dir: str = DEFAULT_DIR,
    print_result: bool = True,
) -> dict[str, Any]:
    """
    Upload a fragpipe-TMT dataset through the /api/jobs/proteomics/ endpoint and update the annotation job.

    Parameters
    ----------
    protein_abundance_file : str
        Path to the protein abundance file.
    experiment_annotation_file : str
        Path to the experiment annotation file.
    annotation_job_id : str
        ID of the job associated with the annotation dataset.
    proteomics_dataset_type : DatasetTypes
        Type of the proteomics dataset (we only support fragpipe-TMT currently).
    user_dir : str
        User directory for authentication state.
    print_result : bool, optional
        Whether to print the result of the upload operation, by default True.

    Returns
    -------
    dict
        A json response with annotationID and proteomicsID.
    """

    abundance_required_headers = ["Index", "NumberPSM", "ProteinID", "MaxPepProb", "ReferenceIntensity"]
    with open(protein_abundance_file, "r") as file:
        first_line = file.readline().strip()
        if not all(header in first_line for header in abundance_required_headers):
            print("Error: The protein abundance file does not contain the required headers.")
            return {}

    state, auth_header = authenticate(user_dir)
    url = state.url + UPLOAD_PROTEIN_ENDPOINT

    if annotation_job_id:
        annotation_url = state.url + GET_ANNOTATION.replace(":id", annotation_job_id)
        annotation_response = requests.get(annotation_url, headers=auth_header)

        if annotation_response.status_code != HTTP_STATUS_OK:
            print(
                f"The annotation with ID {annotation_job_id} does not exist"
            )
            return {}

    job_payload = {
        "protein_abundance_file": Path(protein_abundance_file).name,
        "proteomics_dataset_type": proteomics_dataset_type.value,
        "assembly": "N/A",
    }

    files = [_package_filename(protein_abundance_file)]
    if experiment_annotation_file:
        files.append(_package_filename(experiment_annotation_file))

    response = requests.post(
        url, headers=auth_header, files=files, data={"job": json.dumps(job_payload)}
    )

    if response.status_code == HTTP_STATUS_OK:
        proteomics_response_data = response.json()
        print("\nProteomics Upload response:", json.dumps(proteomics_response_data, indent=4))
        proteomics_job_id = proteomics_response_data.get("_id")

        update_annotation_url = state.url + GET_ANNOTATION.replace(":id", annotation_job_id)
        update_annotation_payload = {"proteomicsID": proteomics_job_id}
        update_annotation_response = requests.patch(
            update_annotation_url, headers=auth_header, json=update_annotation_payload
        )

        if update_annotation_response.status_code != HTTP_STATUS_OK:
            print(
                f"Failed to update annotation job. Status code: {update_annotation_response.status_code}"
            )

        update_proteomics_url = str(
            state.url + UPLOAD_PROTEIN_ENDPOINT + proteomics_job_id
        )
        update_proteomics_payload = {"annotationID": annotation_job_id}
        update_proteomics_response = requests.patch(
            update_proteomics_url, headers=auth_header, json=update_proteomics_payload
        )

        if update_proteomics_response.status_code != HTTP_STATUS_OK:
            print(
                f"Failed to update proteomics job. Status code: {update_proteomics_response.status_code}"
            )

        final_response = {"annotationID": annotation_job_id, "proteomicsID": proteomics_job_id}
        if print_result:
            print("\nLink established successfully.\n")
            print(json.dumps(final_response, indent=4))

        return final_response
    else:
        raise Exception(f"Upload failed with status code {response.status_code}: {response.text}")


#  subparsers is a public class of argparse but is named with a
#  leading underscore, which is a design flaw.  The noqas on the helper methods below
#  below suppress the warnings about this.


def _add_login_subparser(subparsers: argparse._SubParsersAction) -> None:  # noqa: SLF001
    """Add subparser for login command."""
    login_parser = subparsers.add_parser("login", help="Authenticate with the Bystro API")
    login_parser.add_argument(
        "--host",
        required=True,
        help="Host of the Bystro API server, e.g. https://bystro-dev.emory.edu",
    )
    login_parser.add_argument(
        "--port", type=int, default=443, help="Port of the Bystro API server, e.g. 443"
    )
    login_parser.add_argument("--email", required=True, help="Email to login with")
    login_parser.add_argument("--password", required=True, help="Password to login with")
    login_parser.add_argument("--dir", default=DEFAULT_DIR, help="Where to save Bystro API login state")
    login_parser.set_defaults(func=login)


def _add_upload_proteomics_dataset_subparser(
    subparsers: argparse._SubParsersAction,
) -> None:  # noqa: SLF001
    """Add subparser for upload_proteomics_dataset command."""
    upload_proteomics_dataset_parser = subparsers.add_parser(
        "upload-proteomics-dataset", help="Upload a Fragpipe TMT proteomics dataset"
    )
    upload_proteomics_dataset_parser.add_argument(
        "--protein-abundance-file",
        required=True,
        type=str,
        help="Protein abundance file (currently only Fragpipe TMT .tsv's accepted.)",
    )
    upload_proteomics_dataset_parser.add_argument(
        "--experiment-annotation-file",
        required=False,
        type=str,
        help="Experiment annotation file (optional)",
    )
    upload_proteomics_dataset_parser.add_argument(
        "--annotation-job-id",
        required=False,
        help="Annotation job ID to associate with the proteomics dataset (optional)."
    )
    upload_proteomics_dataset_parser.add_argument(
        "--proteomics-dataset-type",
        type=str,
        default="fragpipe_TMT",
        help="Type of proteomics dataset (default: fragpipe-TMT).",
    )
    upload_proteomics_dataset_parser.add_argument(
        "--dir", default=DEFAULT_DIR, help="Where Bystro API login state is saved"
    )

    def wrapper(args):
        sanitized_type = args.proteomics_dataset_type.replace('-', '_')
        try:
            dataset_type_enum = DatasetTypes[sanitized_type]
        except KeyError:
            raise ValueError(f"Invalid proteomics dataset type: {args.proteomics_dataset_type}")

        upload_proteomics_dataset(
            args.protein_abundance_file,
            args.experiment_annotation_file,
            args.annotation_job_id,
            dataset_type_enum,
            args.dir,
            True,
        )

    upload_proteomics_dataset_parser.set_defaults(func=wrapper)


def _configure_parser() -> argparse.ArgumentParser:
    """Configure parser for command line arguments."""
    parser = argparse.ArgumentParser(
        prog="bystro-proteomics-api",
        description="Bystro CLI tool for interacting with proteomics service.",
    )
    subparsers = parser.add_subparsers(title="commands")
    _add_login_subparser(subparsers)
    _add_upload_proteomics_dataset_subparser(subparsers)

    return parser


def main() -> None:
    """Run the proteomics CLI."""
    parser = _configure_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:  # noqa: BLE001
            print(f"\nSomething went wrong:\t{e}\n")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
