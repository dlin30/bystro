"""Provide a CLI for proteomics analysis."""
import argparse
from pathlib import Path
from typing import Any, BinaryIO

import requests
from bystro.api.cli import DEFAULT_DIR, authenticate, login
from msgspec import json as mjson
from enum import Enum

# ruff: noqa: T201

UPLOAD_PROTEIN_ENDPOINT = "/api/jobs/proteomics/"
GET_ANNOTATION = "/api/jobs/:id"
GET_UUID = "/api/jobs/generateJobID"
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
    "fragpipe-TMT"
    "somascan"


def upload_proteomics_dataset(
    protein_abundance_file: str,
    experiment_annotation_file: str,
    annotation_job_id: str,
    proteomics_dataset_type: DatasetTypes,
    user_dir: str,
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

    if annotation_job_id:
        annotation_url = str(state.url / Path(GET_ANNOTATION.replace(":id", annotation_job_id)))
        annotation_response = requests.get(annotation_url, headers=auth_header)

        if annotation_response.status_code != HTTP_STATUS_OK:
            print(
                f"The annotation with ID {annotation_job_id} does not exist"
            )
            return {}

    url = str(state.url / Path(UPLOAD_PROTEIN_ENDPOINT))
    payload = {
        "job": mjson.encode(
            {
                "protein_abundance_file": Path(protein_abundance_file),
                "proteomics_dataset_type": proteomics_dataset_type,
            }
        )
    }

    files_to_upload = [protein_abundance_file, experiment_annotation_file]
    files = [_package_filename(filename) for filename in files_to_upload]

    response = requests.post(
        url, headers=auth_header, data=payload, files=files, timeout=ONE_HOUR_IN_SECONDS
    )

    if response.status_code == HTTP_STATUS_OK:
        proteomics_response_data = response.json()
        proteomics_job_id = proteomics_response_data.get("_id")

        update_annotation_url = str(state.url / Path(GET_ANNOTATION.replace(":id", annotation_job_id)))
        update_annotation_payload = {"proteomicsID": proteomics_job_id}
        update_annotation_response = requests.patch(
            update_annotation_url, headers=auth_header, json=update_annotation_payload
        )

        if update_annotation_response.status_code != HTTP_STATUS_OK:
            print(
                f"Failed to update annotation job. Status code: {update_annotation_response.status_code}"
            )

        update_proteomics_url = str(
            state.url / Path(UPLOAD_PROTEIN_ENDPOINT + proteomics_job_id)
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
            print(mjson.format(final_response, indent=4))

        return final_response

    else:
        msg = f"Proteomics job creation failed with response status: {response.status_code}. Error: \n{response.text}\n"
        raise RuntimeError(msg)


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
        help="Experiment annotation file (currently only Fragpipe format accepted.)",
    )
    upload_proteomics_dataset_parser.add_argument(
        "--dir", default=DEFAULT_DIR, help="Where Bystro API login state is saved"
    )

    def wrapper(args):
        upload_proteomics_dataset(
            args.protein_abundance_file,
            args.experiment_annotation_file,
            DatasetTypes[args.proteomics_dataset_type.upper()],
            args.dir,
            True,
        )

    upload_proteomics_dataset_parser.set_defaults(func=wrapper, command="upload-proteomics-dataset")


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
