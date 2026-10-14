"""Setup profiles for magnification calibration (issue #35)."""
from fastapi import APIRouter, HTTPException

from .. import db, setups
from ..schemas import SetupIn, SetupOut

router = APIRouter(prefix="/setups", tags=["setups"])


def _get_or_404(conn, setup_id: int):
    row = setups.get_setup(conn, setup_id)
    if row is None:
        raise HTTPException(404, "setup not found")
    return row


@router.get("", response_model=list[SetupOut])
def list_all_setups():
    """Every calibrated microscope + phone setup, by name."""
    with db.session() as conn:
        return [SetupOut.from_row(r) for r in setups.list_setups(conn)]


@router.post("", response_model=SetupOut, status_code=201)
def create_new_setup(body: SetupIn):
    """Calibrate a setup: micrometer photo measured at `calibration_objective`."""
    with db.session() as conn:
        try:
            setup_id = setups.create_setup(
                conn, body.name, body.um_per_px, body.calibration_objective, body.phone_resolution)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return SetupOut.from_row(setups.get_setup(conn, setup_id))


@router.get("/{setup_id}", response_model=SetupOut)
def get_setup(setup_id: int):
    with db.session() as conn:
        return SetupOut.from_row(_get_or_404(conn, setup_id))


@router.delete("/{setup_id}", status_code=204)
def delete_existing_setup(setup_id: int):
    """Delete a setup that no slide uses anymore."""
    with db.session() as conn:
        try:
            setups.delete_setup(conn, setup_id)
        except KeyError:
            raise HTTPException(404, "setup not found")
        except ValueError as exc:
            raise HTTPException(409, str(exc))
    return None
