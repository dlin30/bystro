from msgspec import Struct, json as mjson
import datetime
import os
import requests


from bystro.api.auth import authenticate

JOB_TYPE_ROUTE_MAP = {
    "all": "/list/all",
    "public": "/list/all/public",
    "shared": "/list/shared",
    "incomplete": "/list/incomplete",
    "completed": "/list/completed",
    "failed": "/list/failed",
}

class JobBasicResponse(Struct, rename="camel"):
    """
    The basic job information, returned in job list commands

    Attributes
    ----------
    _id : str
        The id of the job.
    name : str
        The name of the job.
    createdAt : str
        The date the job was created.
    """

    _id: str
    name: str
    createdAt: datetime.datetime


class UserProfile(Struct, rename="camel"):
    """
    The response body for fetching the user profile.

    Attributes
    ----------
    options : dict
        The user options.
    _id : str
        The id of the user.
    name : str
        The name of the user.
    email : str
        The email of the user.
    accounts : list[str]
        The accounts of the user.
    role : str
        The role of the user.
    lastLogin : str
        The date the user last logged in.
    """

    _id: str
    options: dict
    name: str
    email: str
    accounts: list[str]
    role: str
    lastLogin: datetime.datetime


def get_jobs(job_type=None, job_id=None, print_result=True
) -> list[JobBasicResponse] | dict:
    """
    Fetches the jobs for the given job type, or a single job if a job id is specified.

    Parameters
    ----------
    bystro_credentials_dir : str
        The directory where the Bystro API login state is saved.
    job_type : str, optional
        The type of jobs to fetch.
    job_id : str, optional
        The ID of a specific job to fetch.
    print_result : bool, optional
        Whether to print the result of the job fetch operation, by default True.

    Returns
    -------
    dict or list[JobBasicResponse]
        The response from the server.
    """
    state, auth_header = authenticate()
    url = state.url + "/api/jobs"

    if not (job_id or job_type):
        raise ValueError("Please specify either a job id or a job type")

    if job_id and job_type:
        raise ValueError("Please specify either a job id or a job type, not both")

    if not job_id and job_type not in JOB_TYPE_ROUTE_MAP.keys():
        raise ValueError(
            f"Invalid job type: {job_type}. Valid types are: {', '.join(JOB_TYPE_ROUTE_MAP.keys())}"
        )

    url = url + f"/{job_id}" if job_id else url + JOB_TYPE_ROUTE_MAP[job_type]

    if print_result:
        if job_id:
            print(f"\nFetching job with id:\t{job_id}")
        else:
            print(f"\nFetching jobs of type:\t{job_type}")

    response = requests.get(url, headers=auth_header, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(
            f"Fetching jobs failed with response status: {response.status_code}. Error: {response.text}"
        )

    if print_result:
        print("\nJob(s) fetched successfully: \n")
        print(mjson.format(response.text, indent=4))
        print("\n")

    if job_id:
        job = mjson.decode(response.text, type=dict)
        # MongoDB doesn't support '.' in field names,
        # so we neede to convert the config to string before saving
        # so we decode the nested json here
        job["config"] = mjson.decode(job["config"])
        return job

    return mjson.decode(response.text, type=list[JobBasicResponse])


def create_job(files, assembly, index=True, print_result=True
) -> dict:
    """
    Creates a job for the given files.

    Parameters
    ----------
    files : list[str]
        List of file paths for job creation.
    assembly : str
        Genome assembly (e.g., hg19, hg38).
    index : bool, optional
        Whether to create a search index for the annotation, by default True.
    print_result : bool, optional
        Whether to print the result of the job creation operation, by default True.

    Returns
    -------
    dict
        The newly created job.
    """
    state, auth_header = authenticate()
    url = state.url + "/api/jobs/upload/"

    payload = {
        "job": mjson.encode(
            {
                "assembly": assembly,
                "options": {"index": index},
            }
        )
    }

    files = []
    for file in files:
        files.append(
            (
                "file",
                (
                    os.path.basename(file),
                    open(file, "rb"),  # noqa: SIM115
                    "application/octet-stream",
                ),
            )
        )

    if print_result:
        print(f"\nCreating jobs for files: {','.join(map(lambda x: x[1][0], files))}\n")

    response = requests.post(
        url, headers=auth_header, data=payload, files=files, timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Job creation failed with response status: {response.status_code}.\
                Error: \n{response.text}\n"
        )

    if print_result:
        print("\nJob creation successful:\n")
        print(mjson.format(response.text, indent=4))
        print("\n")

    return response.json()


def query(job_id, query, size=10, from_=0):
    """
    Performs a query search within the specified job with the given arguments.

    Parameters
    ----------
    query : str, required
        The search query string to be used for fetching data.
    size : int, optional
        The number of records to retrieve in the query response.
    from_ : int, optional
        The record offset from which to start retrieval in the query.
    job_id : str, required
        The unique identifier of the job to query.

    Returns
    -------
    QueryResults
        The queried results
    """

    state, auth_header = authenticate()

    try:
        query_payload = {
            "from": from_,
            "query": {
                "bool": {
                    "must": {
                        "query_string": {
                            "default_operator": "AND",
                            "query": query,
                            "lenient": True,
                            "phrase_slop": 5,
                            "tie_breaker": 0.3,
                        }
                    }
                }
            },
            "size": size,
        }

        response = requests.post(
            state.url + f"/api/jobs/{job_id}/search",
            headers=auth_header,
            json={"id": job_id, "searchBody": query_payload},
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(
                (f"Query failed with status: {response.status_code}. "
                f"Error: \n{response.text}\n")
            )

        query_results = response.json()

        print("\nQuery Results:")
        print(mjson.format(mjson.encode(query_results), indent = 4))

    except Exception as e:
        sys.stderr.write(f"Query failed: {e}\n")
