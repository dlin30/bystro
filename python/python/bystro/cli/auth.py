import argparse
import os

import requests

from msgspec import Struct, json as mjson

DEFAULT_DIR = os.path.expanduser("~/.bystro")
STATE_FILE = "bystro_authentication_token.json"


class SignupResponse(Struct, rename="camel"):
    """
    The response body for signing up for Bystro.

    Attributes
    ----------
    access_token : str
        The access token, which authorizes further API requests
    """

    access_token: str


class LoginResponse(Struct, rename="camel"):
    """
    The response body for logging in to Bystro.

    Attributes
    ----------
    access_token : str
        The access token, which authorizes further API requests
    """

    access_token: str


class CachedAuth(Struct, rename="camel"):
    """
    The authentication state.

    Attributes
    ----------
    email : str
        The email of the user.
    access_token : str
        The access token, which authorizes further API requests
    url : str
        The url of the Bystro server.
    """

    email: str
    access_token: str
    url: str


def _fq_host(args: argparse.Namespace) -> str:
    """
    Returns the fully qualified host, e.g. https://bystro-dev.emory.edu:443

    Parameters
    ----------
    args : argparse.Namespace
        The arguments passed to the command.

    Returns
    -------
    str
        The fully qualified host.
    """
    return f"{args.host}:{args.port}"


def load_state(bystro_credentials_dir: str = DEFAULT_DIR) -> CachedAuth | None:
    """
    Loads the authentication state from the state directory.

    Parameters
    ----------
    bystro_credentials_dir : str
        The directory where the authentication state is saved.

    Returns
    -------
    CachedAuth | None
        The authentication state, or None if the state file doesn't exist.
    """
    path = os.path.join(bystro_credentials_dir, STATE_FILE)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return mjson.decode(f.read(), type=CachedAuth)

    return None


def save_state(data: CachedAuth, bystro_credentials_dir: str = DEFAULT_DIR, print_result=True) -> None:
    """
    Saves the authentication state to a file.

    Parameters
    ----------
    data : CachedAuth
        The data to save.
    bystro_credentials_dir : str
        The directory where the authentication state will be saved.
    print_result : bool, optional
        Whether to print the result of the save operation, by default True.

    Returns
    --------
    None
    """
    if not os.path.exists(bystro_credentials_dir):
        os.makedirs(bystro_credentials_dir, exist_ok=True)

    save_path = os.path.join(bystro_credentials_dir, STATE_FILE)
    encoded_data = mjson.encode(data).decode("utf-8")

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(encoded_data)

    if print_result:
        print(
            f"\nSaved auth credentials to {save_path}:\n{mjson.format(encoded_data, indent=4)}"
        )


def signup(args: argparse.Namespace, print_result=True) -> CachedAuth:
    """
    Signs up for Bystro with the given email, name, and password. Additionally, logs in and
    saves the credentials, to enable API calls without re-authenticating.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments passed to the command.
    print_result : bool, optional
        Whether to print the result of the signup operation, by default True.

    Returns
    -------
    CachedAuth
        The cached authentication state.
    """
    if print_result:
        print(f"\nSigning up for Bystro with email: {args.email}, name: {args.name}")

    fq_host = _fq_host(args)
    url = f"{fq_host}/api/user"

    data = {"email": args.email, "name": args.name, "password": args.password}

    response = requests.put(url, data=data, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"Login failed with response status: {response.status_code}. Error: \n{response.text}\n"
        )

    res = mjson.decode(response.text, type=SignupResponse)
    state = CachedAuth(
        access_token=res.access_token,
        url=fq_host,
        email=args.email,
    )

    save_state(
        state,
        args.dir,
        print_result,
    )

    if print_result:
        print("\nSignup & authentication successful. You may now use the Bystro API!\n")

    return state


def login(args: argparse.Namespace, print_result=True) -> CachedAuth:
    """
    Logs in to the server and saves the authentication state to a file.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments passed to the command.
    print_result : bool, optional
        Whether to print the result of the login operation, by default True.

    Returns
    -------
    CachedAuth
        The cached authentication state.
    """
    fq_host = _fq_host(args)

    if print_result:
        print(f"\nLogging into {fq_host} with email: {args.email}.")

    url = f"{fq_host}/api/user/auth/local"

    body = {"email": args.email, "password": args.password}

    response = requests.post(url, data=body, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"Login failed with response status: {response.status_code}. Error: \n{response.text}\n"
        )

    res = mjson.decode(response.text, type=LoginResponse)
    state = CachedAuth(access_token=res.access_token, url=fq_host, email=args.email)
    save_state(state, args.dir, print_result)

    if print_result:
        print("\nLogin successful. You may now use the Bystro API!\n")

    return state


def authenticate(dir_path: str) -> tuple[CachedAuth, dict]:
    """
    Authenticates the user and returns the url, auth header, and email.

    Parameters
    ----------
    args : argparse.Namespace
        The arguments passed to the command.

    Returns
    -------
    tuple[CachedAuth, dict]
        The cached auth credentials and auth header
    """
    state = load_state(dir_path)

    if not state:
        raise ValueError("\n\nYou are not logged in. Please login first.\n")

    header = {"Authorization": f"Bearer {state.access_token}"}
    return state, header